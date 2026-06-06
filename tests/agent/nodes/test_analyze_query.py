from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from agent.nodes.analyze_query import make_analyze_query_node

_MOD = "agent.nodes.analyze_query"


# ── Helpers ───────────────────────────────────────────────────────────

def _intent(**kw: object) -> dict:
    return {
        "intent": "lookup",
        "complexity": "simple",
        "has_judgment_request": False,
        "has_specific_article": False,
        "law_name": None,
        "article_no": None,
        "reason": "test",
        **kw,
    }


def _chain(return_value: object) -> MagicMock:
    m = MagicMock()
    m.invoke.return_value = return_value
    return m


def _state(question: str = "test") -> dict:
    return {
        "question": question,
        "intent": "",
        "complexity": "",
        "rewritten_queries": [],
        "documents": [],
        "generation": "",
        "retry_count": 0,
        "max_retries": 3,
        "regenerate_count": 0,
        "max_regenerates": 2,
        "halt_reason": "",
        "judgment_api_token": "",
        "messages": [],
    }


@contextmanager  # type: ignore[misc]
def _all_chains(
    intent_rv: dict,
    decompose_rv: dict | None = None,
    hyde_content: str = "假設條文",
    rewrite_content: str = "改寫後查詢",
):
    """四個 chain builder 的完整 mock，便於每個測試只調整需要的部分。"""
    with (
        patch(
            f"{_MOD}._make_intent_chain",
            return_value=_chain(intent_rv),
        ),
        patch(
            f"{_MOD}._make_decompose_chain",
            return_value=_chain(
                decompose_rv or {"sub_queries": []}
            ),
        ),
        patch(
            f"{_MOD}._make_hyde_chain",
            return_value=_chain(
                MagicMock(content=hyde_content)
            ),
        ),
        patch(
            f"{_MOD}._make_rewrite_chain",
            return_value=_chain(
                MagicMock(content=rewrite_content)
            ),
        ),
    ):
        yield


@pytest.fixture
def llm() -> MagicMock:
    return MagicMock()


# ── intent + complexity 寫入 State ────────────────────────────────────

def test_intent_and_complexity_written_to_result(llm: MagicMock) -> None:
    ir = _intent(intent="procedural", complexity="simple")
    with _all_chains(ir):
        result = make_analyze_query_node(llm)(_state())
    assert result["intent"] == "procedural"
    assert result["complexity"] == "simple"


# ── lookup 分支 ────────────────────────────────────────────────────────

def test_lookup_with_article_uses_direct_lookup(
    llm: MagicMock,
) -> None:
    ir = _intent(
        intent="lookup",
        has_specific_article=True,
        law_name="民法",
        article_no="第 184 條",
    )
    with _all_chains(ir):
        result = make_analyze_query_node(llm)(_state())

    queries = result["rewritten_queries"]
    assert len(queries) == 1
    assert queries[0]["strategy"] == "law:direct_lookup"
    assert queries[0]["law_name"] == "民法"
    assert queries[0]["article_no"] == "第 184 條"


def test_lookup_without_article_uses_hyde(llm: MagicMock) -> None:
    ir = _intent(intent="lookup", has_specific_article=False)
    with _all_chains(ir, hyde_content="假設侵權條文"):
        result = make_analyze_query_node(llm)(_state())

    queries = result["rewritten_queries"]
    assert len(queries) == 1
    assert queries[0]["strategy"] == "law:hyde"
    assert queries[0]["query"] == "假設侵權條文"


# ── diagnostic 分支 ───────────────────────────────────────────────────

def test_diagnostic_uses_graph_expand(llm: MagicMock) -> None:
    ir = _intent(intent="diagnostic")
    with _all_chains(ir):
        result = make_analyze_query_node(llm)(_state())

    queries = result["rewritten_queries"]
    assert len(queries) == 1
    assert queries[0]["strategy"] == "law:graph_expand"


# ── procedural 分支 ───────────────────────────────────────────────────

def test_procedural_uses_rewritten_semantic(llm: MagicMock) -> None:
    ir = _intent(intent="procedural")
    with _all_chains(ir, rewrite_content="訴訟提起方式"):
        result = make_analyze_query_node(llm)(_state())

    queries = result["rewritten_queries"]
    assert len(queries) == 1
    assert queries[0]["strategy"] == "law:semantic"
    assert queries[0]["query"] == "訴訟提起方式"


# ── comparison / complex → decompose ─────────────────────────────────

def test_comparison_calls_decompose(llm: MagicMock) -> None:
    ir = _intent(intent="comparison", complexity="simple")
    decompose = {
        "sub_queries": [
            {
                "query": "民事責任",
                "strategy": "law:semantic",
                "law_name": None,
                "article_no": None,
            },
            {
                "query": "刑事責任",
                "strategy": "law:semantic",
                "law_name": None,
                "article_no": None,
            },
        ]
    }
    with _all_chains(ir, decompose_rv=decompose):
        result = make_analyze_query_node(llm)(_state())

    assert len(result["rewritten_queries"]) == 2


def test_complex_intent_always_calls_decompose(llm: MagicMock) -> None:
    ir = _intent(intent="diagnostic", complexity="complex")
    decompose = {
        "sub_queries": [
            {
                "query": "q1",
                "strategy": "law:graph_expand",
                "law_name": None,
                "article_no": None,
            },
            {
                "query": "q2",
                "strategy": "law:semantic",
                "law_name": None,
                "article_no": None,
            },
        ]
    }
    with _all_chains(ir, decompose_rv=decompose):
        result = make_analyze_query_node(llm)(_state())

    assert len(result["rewritten_queries"]) == 2


# ── judgment 補加 ─────────────────────────────────────────────────────

def test_judgment_request_appends_tavily(llm: MagicMock) -> None:
    ir = _intent(intent="diagnostic", has_judgment_request=True)
    with _all_chains(ir):
        result = make_analyze_query_node(llm)(_state())

    strategies = [q["strategy"] for q in result["rewritten_queries"]]
    assert "law:graph_expand" in strategies
    assert "judgment:tavily" in strategies


def test_judgment_not_duplicated_if_already_in_decompose(
    llm: MagicMock,
) -> None:
    ir = _intent(
        intent="comparison",
        complexity="simple",
        has_judgment_request=True,
    )
    decompose = {
        "sub_queries": [
            {
                "query": "q1",
                "strategy": "law:semantic",
                "law_name": None,
                "article_no": None,
            },
            {
                "query": "q2",
                "strategy": "judgment:tavily",
                "law_name": None,
                "article_no": None,
            },
        ]
    }
    with _all_chains(ir, decompose_rv=decompose):
        result = make_analyze_query_node(llm)(_state())

    strategies = [q["strategy"] for q in result["rewritten_queries"]]
    assert strategies.count("judgment:tavily") == 1
