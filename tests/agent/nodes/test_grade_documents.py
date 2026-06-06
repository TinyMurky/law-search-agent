from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document

from agent.nodes.grade_documents import (
    make_grade_documents_node,
    route_after_grade,
)

_MOD = "agent.nodes.grade_documents"


# ── Helpers ───────────────────────────────────────────────────────────

def _doc(content: str = "條文內容") -> Document:
    return Document(
        page_content=content,
        metadata={"node_id": "B0000001#第 1 條"},
    )


def _grader_result(score: str, reason: str = "test") -> dict:
    return {"score": score, "reason": reason}


def _state(
    documents: list[Document] | None = None,
    retry_count: int = 0,
    max_retries: int = 2,
) -> dict:
    return {
        "question": "侵權行為的構成要件？",
        "intent": "lookup",
        "complexity": "simple",
        "rewritten_queries": [],
        "documents": documents or [],
        "generation": "",
        "retry_count": retry_count,
        "max_retries": max_retries,
        "regenerate_count": 0,
        "max_regenerates": 2,
        "halt_reason": "",
        "judgment_api_token": "",
        "messages": [],
    }


@pytest.fixture
def llm() -> MagicMock:
    return MagicMock()


# ── grade_documents_node ──────────────────────────────────────────────

def test_all_relevant_docs_are_kept(llm: MagicMock) -> None:
    docs = [_doc("條文 A"), _doc("條文 B")]
    mock_grader = MagicMock()
    mock_grader.invoke.return_value = _grader_result("yes")

    with patch(f"{_MOD}._make_grader_chain", return_value=mock_grader):
        node = make_grade_documents_node(llm)
        result = node(_state(documents=docs))

    assert len(result["documents"]) == 2


def test_irrelevant_docs_are_filtered(llm: MagicMock) -> None:
    docs = [_doc("條文 A"), _doc("條文 B"), _doc("條文 C")]
    mock_grader = MagicMock()
    mock_grader.invoke.side_effect = [
        _grader_result("yes"),
        _grader_result("no", "與問題無關"),
        _grader_result("yes"),
    ]

    with patch(f"{_MOD}._make_grader_chain", return_value=mock_grader):
        node = make_grade_documents_node(llm)
        result = node(_state(documents=docs))

    assert len(result["documents"]) == 2


def test_all_irrelevant_returns_empty(llm: MagicMock) -> None:
    docs = [_doc("條文 A"), _doc("條文 B")]
    mock_grader = MagicMock()
    mock_grader.invoke.return_value = _grader_result("no", "不相關")

    with patch(f"{_MOD}._make_grader_chain", return_value=mock_grader):
        node = make_grade_documents_node(llm)
        result = node(_state(documents=docs))

    assert result["documents"] == []


def test_empty_input_skips_grader(llm: MagicMock) -> None:
    mock_grader = MagicMock()

    with patch(f"{_MOD}._make_grader_chain", return_value=mock_grader):
        node = make_grade_documents_node(llm)
        result = node(_state(documents=[]))

    mock_grader.invoke.assert_not_called()
    assert result["documents"] == []


def test_direct_lookup_skips_grader(llm: MagicMock) -> None:
    doc = Document(
        page_content="民法第 184 條條文",
        metadata={
            "node_id": "B0000001#第 184 條",
            "strategy": "law:direct_lookup",
        },
    )
    mock_grader = MagicMock()

    with patch(f"{_MOD}._make_grader_chain", return_value=mock_grader):
        node = make_grade_documents_node(llm)
        result = node(_state(documents=[doc]))

    mock_grader.invoke.assert_not_called()
    assert len(result["documents"]) == 1


def test_direct_lookup_mixed_with_semantic(llm: MagicMock) -> None:
    direct_doc = Document(
        page_content="直查條文",
        metadata={
            "node_id": "B0000001#第 184 條",
            "strategy": "law:direct_lookup",
        },
    )
    semantic_doc = Document(
        page_content="語意搜尋條文",
        metadata={
            "node_id": "B0000001#第 185 條",
            "strategy": "law:semantic",
        },
    )
    mock_grader = MagicMock()
    mock_grader.invoke.return_value = _grader_result("yes")

    with patch(f"{_MOD}._make_grader_chain", return_value=mock_grader):
        node = make_grade_documents_node(llm)
        result = node(_state(documents=[direct_doc, semantic_doc]))

    mock_grader.invoke.assert_called_once()
    assert len(result["documents"]) == 2


def test_grader_called_once_per_document(llm: MagicMock) -> None:
    docs = [_doc(f"條文 {i}") for i in range(4)]
    mock_grader = MagicMock()
    mock_grader.invoke.return_value = _grader_result("yes")

    with patch(f"{_MOD}._make_grader_chain", return_value=mock_grader):
        node = make_grade_documents_node(llm)
        node(_state(documents=docs))

    assert mock_grader.invoke.call_count == 4


# ── route_after_grade ─────────────────────────────────────────────────

def test_route_to_generate_when_docs_exist() -> None:
    state = _state(documents=[_doc()], retry_count=0)
    assert route_after_grade(state) == "generate"  # type: ignore[arg-type]


def test_route_to_rewrite_when_no_docs_and_retries_left() -> None:
    state = _state(documents=[], retry_count=0, max_retries=2)
    assert route_after_grade(state) == "rewrite_query"  # type: ignore[arg-type]


def test_route_to_force_end_when_no_docs_and_no_retries() -> None:
    state = _state(documents=[], retry_count=2, max_retries=2)
    assert route_after_grade(state) == "force_end"  # type: ignore[arg-type]


def test_route_to_force_end_boundary(retry_count: int = 1) -> None:
    state = _state(documents=[], retry_count=1, max_retries=1)
    assert route_after_grade(state) == "force_end"  # type: ignore[arg-type]
