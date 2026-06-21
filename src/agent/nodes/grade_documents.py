from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Literal

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from agent.state import AgenticRAGState
from agent.strategy_registry import STRATEGY_REGISTRY

logger = logging.getLogger(__name__)

# ── Pydantic schema ───────────────────────────────────────────────────


class RelevanceResult(BaseModel):
    """grade_documents 節點文件相關性評分的輸出結構。"""

    score: Literal["yes", "no"] = Field(description="此文件是否與問題相關")
    reason: str = Field(description="一句話說明判斷依據, 不知道如何判斷的，回答不知道")


# ── Prompt ────────────────────────────────────────────────────────────

_GRADER_SYSTEM = """\
你是一個法律文件相關性評分器。
判斷給定的法律條文是否能協助回答使用者的問題。

評分規則：
- "yes"：條文內容與問題直接相關，或包含回答問題所需的法律概念,
         不知道如含判斷的請先使用 yes
- "no" ：條文內容與問題無關，或只是泛泛的程序條文

注意：不需要條文「完整回答」問題，只要「有助於回答」就算相關。

{format_instructions}
只輸出 JSON，不要其他文字。"""


# ── Chain builder ─────────────────────────────────────────────────────


def _make_grader_chain(
    llm: ChatGoogleGenerativeAI,
) -> Runnable:
    """建立文件相關性評分（relevance grader）的 LLM chain。

    Args:
        llm (ChatGoogleGenerativeAI): 用於評分的 LLM。

    Returns:
        Runnable: 輸入 question 與 document，輸出 RelevanceResult
            對應 dict 的 chain。
    """
    parser = JsonOutputParser(pydantic_object=RelevanceResult)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _GRADER_SYSTEM),
            ("human", "使用者問題：{question}\n\n參考條文：{document}"),
        ]
    )
    return (
        prompt.partial(format_instructions=parser.get_format_instructions())
        | llm
        | parser
    )


# ── Routing ───────────────────────────────────────────────────────────


def route_after_grade(state: AgenticRAGState) -> str:
    """grade_documents 後的路由，供 LangGraph conditional edge 使用。

    Args:
        state (AgenticRAGState): 目前的 Graph 狀態，取用
            grade_passed、rewrite_count、max_rewrites 欄位。

    Returns:
        str: 下一個節點名稱，"generate"、"rewrite_query" 或
            "force_end"。
    """
    if state["grade_passed"]:
        return "generate"
    if state["rewrite_count"] < state["max_rewrites"]:
        return "rewrite_query"
    return "force_end"


# ── Node factory ──────────────────────────────────────────────────────


def make_grade_documents_node(
    llm: ChatGoogleGenerativeAI,
) -> Callable[[AgenticRAGState], dict[str, object]]:
    """建立 grade_documents 節點，注入 LLM 依賴。

    Args:
        llm (ChatGoogleGenerativeAI): 節點內 grader chain 使用的 LLM。

    Returns:
        Callable[[AgenticRAGState], dict[str, object]]:
            grade_documents 節點函式。
    """
    grader = _make_grader_chain(llm)

    def grade_documents_node(
        state: AgenticRAGState,
    ) -> dict[str, object]:
        question = state["question"]
        documents = state["documents"]
        relevant_docs = []

        for i, doc in enumerate(documents):
            # 這邊先寫死哪些 strategy 需要被 grading
            strategy = str(doc.metadata.get("strategy", ""))
            config = STRATEGY_REGISTRY.get(
                strategy, {"requires_grading": True}
            )

            if not config["requires_grading"]:
                relevant_docs.append(doc)
                logger.info(f"[grade] Chunk {i + 1}：✓ {strategy}（跳過）")
                continue

            result: dict[str, object] = grader.invoke(
                {
                    "question": question,
                    "document": doc.page_content,
                }
            )

            if result["score"] == "yes":
                relevant_docs.append(doc)
                logger.info(f"[grade] Chunk {i + 1}：✓ 相關")
            else:
                logger.info(
                    f"[grade] Chunk {i + 1}：" f"✗ 不相關（{result['reason']}）"
                )

        logger.info(
            f"[grade] 保留 {len(relevant_docs)}" f"/{len(documents)} 個文件"
        )
        return {
            "documents": relevant_docs,
            "grade_passed": len(relevant_docs) > 0,
        }

    return grade_documents_node
