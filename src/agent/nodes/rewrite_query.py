from __future__ import annotations

from collections.abc import Callable

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from agent.state import AgenticRAGState, SubQuery

_REWRITE_SYSTEM = """\
前一次搜尋沒有找到足夠的相關法律資訊。
請從完全不同的角度改寫這個問題，嘗試使用不同的術語或關鍵字。
只輸出一條改寫後的查詢，不要輸出多條，不要說明，不要編號。"""


def _make_rewrite_chain(  # type: ignore[no-untyped-def]
    llm: ChatGoogleGenerativeAI,
):
    """建立換角度改寫查詢的 LLM chain。

    Args:
        llm (ChatGoogleGenerativeAI): 用於改寫查詢的 LLM。

    Returns:
        Runnable: 輸入 question，輸出改寫後查詢字串的 chain。
    """
    prompt = ChatPromptTemplate.from_messages([
        ("system", _REWRITE_SYSTEM),
        ("human", "原始問題：{question}\n\n請換個角度改寫："),
    ])
    return prompt | llm | StrOutputParser()


def make_rewrite_query_node(
    llm: ChatGoogleGenerativeAI,
) -> Callable[[AgenticRAGState], dict[str, object]]:
    """建立 rewrite_query 節點，注入 LLM 依賴。

    Args:
        llm (ChatGoogleGenerativeAI): 節點內 rewrite chain 使用的 LLM。

    Returns:
        Callable[[AgenticRAGState], dict[str, object]]:
            rewrite_query 節點函式。
    """
    rewrite_chain = _make_rewrite_chain(llm)

    def rewrite_query_node(
        state: AgenticRAGState,
    ) -> dict[str, object]:
        question = state["question"]
        new_query: str = rewrite_chain.invoke({"question": question})
        new_rewrite_count = state["rewrite_count"] + 1
        print(
            f"[rewrite] 第 {new_rewrite_count} 次重寫，"
            f"新查詢：{new_query[:60]}..."
        )
        # rewrite 後固定使用 law:semantic（最通用的 fallback 策略）。
        # 未來若需依 intent 選擇 fallback 策略，
        # 可查詢 STRATEGY_REGISTRY（見 law-rag-agent skill）。
        # regenerate_count 重置：換搜尋方向後重新給 regenerate 機會。
        # hallucination_passed 重置：確保下一輪 generate 不誤判為 regenerate。
        return {
            "rewritten_queries": [SubQuery(
                query=new_query,
                strategy="law:semantic",
                law_name=None,
                article_no=None,
            )],
            "rewrite_count": new_rewrite_count,
            "documents": [],
            "regenerate_count": 0,
            "hallucination_passed": True,
        }

    return rewrite_query_node
