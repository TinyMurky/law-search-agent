from unittest.mock import MagicMock, patch

import pytest

from agent.nodes.rewrite_query import make_rewrite_query_node

_MOD = "agent.nodes.rewrite_query"


# ── Helpers ───────────────────────────────────────────────────────────

def _state(
    question: str = "侵權行為的定義？",
    retry_count: int = 0,
) -> dict:
    return {
        "question": question,
        "intent": "lookup",
        "complexity": "simple",
        "rewritten_queries": [],
        "documents": [],
        "generation": "",
        "retry_count": retry_count,
        "max_retries": 3,
        "regenerate_count": 0,
        "max_regenerates": 2,
        "halt_reason": "",
        "judgment_api_token": "",
        "messages": [],
    }


@pytest.fixture
def llm() -> MagicMock:
    return MagicMock()


# ── Tests ─────────────────────────────────────────────────────────────

def test_retry_count_increments(llm: MagicMock) -> None:
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = "改寫後的查詢"

    with patch(f"{_MOD}._make_rewrite_chain", return_value=mock_chain):
        node = make_rewrite_query_node(llm)
        result = node(_state(retry_count=1))

    assert result["retry_count"] == 2


def test_documents_cleared(llm: MagicMock) -> None:
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = "改寫後的查詢"

    with patch(f"{_MOD}._make_rewrite_chain", return_value=mock_chain):
        node = make_rewrite_query_node(llm)
        result = node(_state())

    assert result["documents"] == []


def test_uses_semantic_strategy(llm: MagicMock) -> None:
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = "改寫後的查詢"

    with patch(f"{_MOD}._make_rewrite_chain", return_value=mock_chain):
        node = make_rewrite_query_node(llm)
        result = node(_state())

    queries = result["rewritten_queries"]
    assert len(queries) == 1
    assert queries[0]["strategy"] == "law:semantic"


def test_rewritten_query_from_chain(llm: MagicMock) -> None:
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = "不法侵害他人權利之損害賠償"

    with patch(f"{_MOD}._make_rewrite_chain", return_value=mock_chain):
        node = make_rewrite_query_node(llm)
        result = node(_state())

    assert result["rewritten_queries"][0]["query"] == (
        "不法侵害他人權利之損害賠償"
    )


def test_law_name_and_article_no_are_none(llm: MagicMock) -> None:
    mock_chain = MagicMock()
    mock_chain.invoke.return_value = "改寫後的查詢"

    with patch(f"{_MOD}._make_rewrite_chain", return_value=mock_chain):
        node = make_rewrite_query_node(llm)
        result = node(_state())

    q = result["rewritten_queries"][0]
    assert q["law_name"] is None
    assert q["article_no"] is None
