from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from langchain_core.messages import AIMessage
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from agent.state import AgenticRAGState

# ── Pydantic schemas ──────────────────────────────────────────────────


class HallucinationResult(BaseModel):
    """generate 節點幻覺檢查（hallucination grader）的輸出結構。"""

    score: Literal["yes", "no"] = Field(
        description="答案是否完全根據文件（yes=有根據，no=有幻覺）"
    )
    reason: str = Field(description="一句話說明判斷依據")


class AnswerResult(BaseModel):
    """generate 節點答案品質檢查（answer grader）的輸出結構。"""

    score: Literal["yes", "no"] = Field(
        description="答案是否真正回答了問題（yes=有回答，no=未完整）"
    )
    missing: str = Field(description="缺少什麼資訊（若有回答則填 none）")


# ── Prompts ───────────────────────────────────────────────────────────

_GENERATE_SYSTEM = """\
你是一位專業的法律資訊助理。
只根據以下法律條文回答接下來用戶提出的問題，
找不到相關資訊請明確說明，不要自行推測。

回答時請分成兩段，不要寫「根據你提供的條文」之類的引導句，
直接回答問題本身：

第一段（回答）：以專業口吻直接回答使用者的問題，重點放在
論述與結論，不要在此段逐條覆誦法條原文。每個論點都必須能在
第二段找到對應的法條依據。

第二段（法律依據）：列出第一段各論點所依據的條文，逐條標明
法規名稱、條號與原文內容，作為第一段論述的具體支撐。

條文內容：
{context}"""

_REGENERATE_SYSTEM = """\
你是一位專業的法律資訊助理。
前次回答與條文內容有不一致之處，請重新根據以下條文嚴格回答，
不要加入條文以外的任何資訊。

回答時請分成兩段，不要寫「根據你提供的條文」之類的引導句，
直接回答問題本身：

第一段（回答）：以專業口吻直接回答使用者的問題，重點放在
論述與結論，不要在此段逐條覆誦法條原文。每個論點都必須能在
第二段找到對應的法條依據。

第二段（法律依據）：列出第一段各論點所依據的條文，逐條標明
法規名稱、條號與原文內容，作為第一段論述的具體支撐。


條文內容：
{context}"""

_HALLUCINATION_SYSTEM = """\
你是一個法律答案查核員。
判斷給定的「答案」中，所引用或陳述的法律資訊是否有條文根據。

評分規則：
- "yes"：答案的法律資訊可在條文中找到依據
  （允許說明句、引導句等語言框架，如「根據條文...」「民法第X條規定...」）
- "no" ：答案包含條文中沒有依據的法律聲明或事實推測

{format_instructions}
只輸出 JSON，不要其他文字。"""

_ANSWER_SYSTEM = """\
你是一個法律答案品質評估員。
判斷給定的「答案」是否真正回答了「問題」。

評分規則：
- "yes"：答案確實回答了問題的核心
- "no" ：答案沒有回答問題，或嚴重缺少關鍵資訊

{format_instructions}
只輸出 JSON，不要其他文字。"""


# ── Chain builders ────────────────────────────────────────────────────


def _make_generate_chain(
    llm: ChatGoogleGenerativeAI,
    system_prompt: str,
) -> Runnable:
    """建立依指定 system prompt 生成答案的 LLM chain。

    Args:
        llm (ChatGoogleGenerativeAI): 用於生成答案的 LLM。
        system_prompt (str): 套用的 system prompt
            （一般生成或 regenerate）。

    Returns:
        Runnable: 輸入 context 與 question，輸出答案字串的 chain。
    """
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", system_prompt),
            ("human", "{question}"),
        ]
    )
    return prompt | llm | StrOutputParser()


def _make_hallucination_grader_chain(
    llm: ChatGoogleGenerativeAI,
) -> Runnable:
    """建立幻覺檢查（hallucination grader）的 LLM chain。

    Args:
        llm (ChatGoogleGenerativeAI): 用於檢查的 LLM。

    Returns:
        Runnable: 輸入 documents 與 generation，輸出
            HallucinationResult 對應 dict 的 chain。
    """
    parser = JsonOutputParser(pydantic_object=HallucinationResult)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _HALLUCINATION_SYSTEM),
            ("human", "條文內容：{documents}\n\n答案：{generation}"),
        ]
    )
    return (
        prompt.partial(format_instructions=parser.get_format_instructions())
        | llm
        | parser
    )


def _make_answer_grader_chain(
    llm: ChatGoogleGenerativeAI,
) -> Runnable:
    """建立答案品質檢查（answer grader）的 LLM chain。

    Args:
        llm (ChatGoogleGenerativeAI): 用於檢查的 LLM。

    Returns:
        Runnable: 輸入 question 與 generation，輸出 AnswerResult
            對應 dict 的 chain。
    """
    parser = JsonOutputParser(pydantic_object=AnswerResult)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _ANSWER_SYSTEM),
            ("human", "問題：{question}\n\n答案：{generation}"),
        ]
    )
    return (
        prompt.partial(format_instructions=parser.get_format_instructions())
        | llm
        | parser
    )


# ── Routing ───────────────────────────────────────────────────────────


def route_after_generate(state: AgenticRAGState) -> str:
    """generate 後的路由，供 LangGraph conditional edge 使用。

    Args:
        state (AgenticRAGState): 目前的 Graph 狀態，取用
            hallucination_passed、answer_passed、regenerate_count、
            max_regenerates 欄位。

    Returns:
        str: 下一個節點名稱，"regenerate"、"rewrite_query" 或
            "finish"。
    """
    hallucination_passed = state["hallucination_passed"]
    answer_passed = state["answer_passed"]
    regenerate_count = state["regenerate_count"]
    max_regenerates = state["max_regenerates"]

    if not hallucination_passed:
        if regenerate_count < max_regenerates:
            return "regenerate"
        return "rewrite_query"
    if not answer_passed:
        return "rewrite_query"
    return "finish"


# ── Node factory ──────────────────────────────────────────────────────


def make_generate_node(
    llm: ChatGoogleGenerativeAI,
) -> Callable[[AgenticRAGState], dict[str, object]]:
    """建立 generate 節點，注入 LLM 依賴。

    Args:
        llm (ChatGoogleGenerativeAI): 節點內各 chain 共用的 LLM。

    Returns:
        Callable[[AgenticRAGState], dict[str, object]]: generate
            節點函式。
    """
    generate_chain = _make_generate_chain(llm, _GENERATE_SYSTEM)
    regenerate_chain = _make_generate_chain(llm, _REGENERATE_SYSTEM)
    hallucination_grader = _make_hallucination_grader_chain(llm)
    answer_grader = _make_answer_grader_chain(llm)

    def generate_node(
        state: AgenticRAGState,
    ) -> dict[str, object]:
        question = state["question"]
        texts = (doc.page_content for doc in state["documents"])
        context = "\n---\n".join(texts)

        # 上次幻覺失敗才算 regenerate
        is_regenerate = not state["hallucination_passed"]
        regenerate_count = state["regenerate_count"]
        if is_regenerate:
            regenerate_count += 1

        chain = regenerate_chain if is_regenerate else generate_chain
        payload = {"context": context, "question": question}
        generation: str = chain.invoke(payload)
        print(f"[generate] 生成完成（{len(generation)} 字）")

        # 幻覺 grader
        hall_result: dict[str, object] = hallucination_grader.invoke(
            {
                "documents": context,
                "generation": generation,
            }
        )
        hallucination_passed = hall_result["score"] == "yes"
        print(
            f"[generate] 幻覺檢查："
            f"{'✓' if hallucination_passed else '✗'} "
            f"— {str(hall_result['reason'])[:60]}"
        )

        # answer grader（短路：幻覺不過就不跑，answer_passed 預設 True）
        answer_passed = True
        if hallucination_passed:
            ans_result: dict[str, object] = answer_grader.invoke(
                {
                    "question": question,
                    "generation": generation,
                }
            )
            answer_passed = ans_result["score"] == "yes"
            print(
                f"[generate] 回答品質："
                f"{'✓' if answer_passed else '✗'} "
                f"— {str(ans_result['missing'])[:60]}"
            )

        return {
            "generation": generation,
            "hallucination_passed": hallucination_passed,
            "answer_passed": answer_passed,
            "regenerate_count": regenerate_count,
            "messages": [AIMessage(content=generation)],
        }

    return generate_node
