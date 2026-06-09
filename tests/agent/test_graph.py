from unittest.mock import MagicMock

from agent.graph import _login_node, build_graph
from agent.state import AgenticRAGState


# ── _login_node ───────────────────────────────────────────────────────

def _base_state() -> AgenticRAGState:
    return {  # type: ignore[return-value]
        "question": "",
        "intent": "",
        "complexity": "",
        "rewritten_queries": [],
        "documents": [],
        "grade_passed": False,
        "generation": "",
        "hallucination_passed": True,
        "answer_passed": True,
        "rewrite_count": 0,
        "max_rewrites": 3,
        "regenerate_count": 0,
        "max_regenerates": 2,
        "halt_reason": "",
        "judgment_api_token": "",
        "messages": [],
    }


def test_login_node_sets_empty_token() -> None:
    result = _login_node(_base_state())
    assert result["judgment_api_token"] == ""


def test_login_node_always_returns_empty_token() -> None:
    state = _base_state()
    state["judgment_api_token"] = "old-token"
    result = _login_node(state)
    assert result["judgment_api_token"] == ""


# ── build_graph ───────────────────────────────────────────────────────

def test_build_graph_compiles() -> None:
    llm = MagicMock()
    chunk_builder = MagicMock()
    law_graph = MagicMock()
    graph = build_graph(llm, chunk_builder, law_graph)
    assert graph is not None
