from __future__ import annotations

from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from agent.nodes.analyze_query import make_analyze_query_node
from agent.nodes.force_end import force_end_node
from agent.nodes.generate import make_generate_node, route_after_generate
from agent.nodes.grade_documents import (
    make_grade_documents_node,
    route_after_grade,
)
from agent.nodes.retrieve import make_retrieve_node
from agent.nodes.rewrite_query import make_rewrite_query_node
from agent.state import AgenticRAGState
from ingestion.law_graph.nx_law_graph import NxLawGraph
from ingestion.law_vector.chunk_builder import ChunkBuilder


def _login_node(
    state: AgenticRAGState,
) -> dict[str, str]:
    """Placeholder: 向司法院 API 登入並取得 token。

    Args:
        state (AgenticRAGState): 目前的 Graph 狀態（此節點未使用
            其內容）。

    Returns:
        dict[str, str]: 寫入 judgment_api_token 欄位的 State 更新。
    """
    print("[login] 司法院 API 登入（placeholder）")
    return {"judgment_api_token": ""}


def build_graph(
    llm: ChatGoogleGenerativeAI,
    chunk_builder: ChunkBuilder,
    law_graph: NxLawGraph,
) -> CompiledStateGraph:
    """組裝並編譯 Self-RAG LangGraph。

    Args:
        llm (ChatGoogleGenerativeAI): 注入各節點使用的 LLM。
        chunk_builder (ChunkBuilder): 注入 retrieve 節點的向量
            搜尋依賴。
        law_graph (NxLawGraph): 注入 retrieve 節點的圖查詢依賴。

    Returns:
        CompiledStateGraph: 編譯完成、可直接 invoke 的 LangGraph。
    """
    builder: StateGraph = StateGraph(AgenticRAGState)

    # ── 節點 ──────────────────────────────────────────────────────────
    _analyze = make_analyze_query_node(llm, law_graph)
    _retrieve = make_retrieve_node(chunk_builder, law_graph)
    _grade = make_grade_documents_node(llm)
    _generate = make_generate_node(llm)
    _rewrite = make_rewrite_query_node(llm)

    builder.add_node("login", _login_node)
    builder.add_node("analyze_query", _analyze)  # type: ignore[arg-type]
    builder.add_node("retrieve", _retrieve)  # type: ignore[arg-type]
    builder.add_node("grade_documents", _grade)  # type: ignore[arg-type]
    builder.add_node("generate", _generate)  # type: ignore[arg-type]
    builder.add_node("rewrite_query", _rewrite)  # type: ignore[arg-type]
    builder.add_node("force_end", force_end_node)

    # ── 固定邊 ────────────────────────────────────────────────────────
    builder.add_edge(START, "login")
    builder.add_edge("login", "analyze_query")
    builder.add_edge("analyze_query", "retrieve")
    builder.add_edge("retrieve", "grade_documents")
    builder.add_edge("rewrite_query", "retrieve")
    builder.add_edge("force_end", END)

    # ── 條件邊 ────────────────────────────────────────────────────────
    builder.add_conditional_edges(
        "grade_documents",
        route_after_grade,
        {
            "generate": "generate",
            "rewrite_query": "rewrite_query",
            "force_end": "force_end",
        },
    )
    builder.add_conditional_edges(
        "generate",
        route_after_generate,
        {
            "finish": END,
            "regenerate": "generate",
            "rewrite_query": "rewrite_query",
        },
    )

    return builder.compile()
