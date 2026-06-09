from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from agent.state import AgenticRAGState
from agent.strategy_registry import STRATEGY_REGISTRY


# ── Pydantic schema ───────────────────────────────────────────────────

class RelevanceResult(BaseModel):
    score: Literal["yes", "no"] = Field(
        description="此文件是否與問題相關"
    )
    reason: str = Field(description="一句話說明判斷依據")


# ── Prompt ────────────────────────────────────────────────────────────

_GRADER_SYSTEM = """\
你是一個法律文件相關性評分器。
判斷給定的法律條文是否能協助回答使用者的問題。

評分規則：
- "yes"：條文內容與問題直接相關，或包含回答問題所需的法律概念
- "no" ：條文內容與問題無關，或只是泛泛的程序條文

注意：不需要條文「完整回答」問題，只要「有助於回答」就算相關。

{format_instructions}
只輸出 JSON，不要其他文字。"""


# ── Chain builder ─────────────────────────────────────────────────────

def _make_grader_chain(  # type: ignore[no-untyped-def]
    llm: ChatGoogleGenerativeAI,
):
    parser = JsonOutputParser(pydantic_object=RelevanceResult)
    prompt = ChatPromptTemplate.from_messages([
        ("system", _GRADER_SYSTEM),
        ("human", "問題：{question}\n\n條文：{document}"),
    ])
    return (
        prompt.partial(
            format_instructions=parser.get_format_instructions()
        )
        | llm
        | parser
    )


# ── Routing ───────────────────────────────────────────────────────────

def route_after_grade(state: AgenticRAGState) -> str:
    """grade_documents 後的路由，供 LangGraph conditional edge 使用。"""
    if state["grade_passed"]:
        return "generate"
    if state["rewrite_count"] < state["max_rewrites"]:
        return "rewrite_query"
    return "force_end"


# ── Node factory ──────────────────────────────────────────────────────

def make_grade_documents_node(
    llm: ChatGoogleGenerativeAI,
) -> Callable[[AgenticRAGState], dict[str, object]]:
    """建立 grade_documents 節點，注入 LLM 依賴。"""
    grader = _make_grader_chain(llm)

    def grade_documents_node(
        state: AgenticRAGState,
    ) -> dict[str, object]:
        question = state["question"]
        documents = state["documents"]
        relevant_docs = []

        for i, doc in enumerate(documents):
            strategy = str(doc.metadata.get("strategy", ""))
            config = STRATEGY_REGISTRY.get(
                strategy, {"requires_grading": True}
            )
            if not config["requires_grading"]:
                relevant_docs.append(doc)
                print(f"[grade] Chunk {i + 1}：✓ {strategy}（跳過）")
                continue

            result: dict[str, object] = grader.invoke({
                "question": question,
                "document": doc.page_content,
            })
            if result["score"] == "yes":
                relevant_docs.append(doc)
                print(f"[grade] Chunk {i + 1}：✓ 相關")
            else:
                print(
                    f"[grade] Chunk {i + 1}："
                    f"✗ 不相關（{result['reason']}）"
                )

        print(
            f"[grade] 保留 {len(relevant_docs)}"
            f"/{len(documents)} 個文件"
        )
        return {
            "documents": relevant_docs,
            "grade_passed": len(relevant_docs) > 0,
        }

    return grade_documents_node
