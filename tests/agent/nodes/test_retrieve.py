from unittest.mock import MagicMock

import pytest
from langchain_core.documents import Document

from agent.nodes.retrieve import make_retrieve_node
from agent.state import SubQuery


# ── Helpers ───────────────────────────────────────────────────────────

def _sub_query(
    query: str,
    strategy: str,
    law_name: str | None = None,
    article_no: str | None = None,
) -> SubQuery:
    return SubQuery(
        query=query,
        strategy=strategy,  # type: ignore[arg-type]
        law_name=law_name,
        article_no=article_no,
    )


def _state(sub_queries: list[SubQuery]) -> dict:
    return {
        "question": "test",
        "intent": "lookup",
        "complexity": "simple",
        "rewritten_queries": sub_queries,
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


def _chunk_result(
    pcode: str = "B0000001",
    article_no: str = "第 184 條",
    law_name: str = "民法",
    content: str = "條文內容",
) -> dict:
    return {
        "node_id": f"{pcode}#{article_no}",
        "law_name": law_name,
        "article_no": article_no,
        "content": content,
        "score": 0.9,
    }


def _article_node(
    pcode: str = "B0000001",
    article_no: str = "第 184 條",
    law_name: str = "民法",
) -> dict:
    return {
        "type": "article",
        "pcode": pcode,
        "law_name": law_name,
        "article_no": article_no,
        "content": f"{article_no} 條文",
        "source_pcode": pcode,
        "source_article_no": article_no,
        "source_paragraph": "",
        "law_modified_date": "20210101",
        "created_at": "2026-05-30T00:00:00+00:00",
    }


@pytest.fixture
def mock_builder() -> MagicMock:
    b = MagicMock()
    b.search.return_value = []
    return b


@pytest.fixture
def mock_graph() -> MagicMock:
    g = MagicMock()
    g.find_pcode_by_name.return_value = None
    g.get_node.return_value = None
    g.get_cited_with_edges.return_value = []
    return g


# ── law:semantic / law:hyde ───────────────────────────────────────────

def test_semantic_returns_chunk_results(
    mock_builder: MagicMock, mock_graph: MagicMock
) -> None:
    mock_builder.search.return_value = [_chunk_result()]
    node = make_retrieve_node(mock_builder, mock_graph)
    result = node(_state([_sub_query("侵權行為", "law:semantic")]))

    docs: list[Document] = result["documents"]  # type: ignore[assignment]
    assert len(docs) == 1
    assert "民法" in docs[0].page_content
    assert docs[0].metadata["pcode"] == "B0000001"


def test_hyde_uses_query_directly_for_search(
    mock_builder: MagicMock, mock_graph: MagicMock
) -> None:
    mock_builder.search.return_value = [_chunk_result()]
    node = make_retrieve_node(mock_builder, mock_graph)
    result = node(_state([
        _sub_query("假設條文片段（HyDE 已生成）", "law:hyde")
    ]))

    mock_builder.search.assert_called_once_with(
        "假設條文片段（HyDE 已生成）", k=5
    )
    assert len(result["documents"]) == 1


# ── law:direct_lookup ─────────────────────────────────────────────────

def test_direct_lookup_found_returns_document(
    mock_builder: MagicMock, mock_graph: MagicMock
) -> None:
    mock_graph.find_pcode_by_name.return_value = "B0000001"
    mock_graph.get_node.return_value = _article_node()
    node = make_retrieve_node(mock_builder, mock_graph)
    result = node(_state([
        _sub_query("", "law:direct_lookup", "民法", "第 184 條")
    ]))

    mock_graph.get_node.assert_called_once_with("B0000001#第 184 條")
    docs = result["documents"]
    assert len(docs) == 1
    assert docs[0].metadata["article_no"] == "第 184 條"


def test_direct_lookup_pcode_not_found_returns_empty(
    mock_builder: MagicMock, mock_graph: MagicMock
) -> None:
    mock_graph.find_pcode_by_name.return_value = None
    node = make_retrieve_node(mock_builder, mock_graph)
    result = node(_state([
        _sub_query("", "law:direct_lookup", "不存在的法律", "第 1 條")
    ]))

    assert result["documents"] == []


def test_direct_lookup_article_not_found_returns_empty(
    mock_builder: MagicMock, mock_graph: MagicMock
) -> None:
    mock_graph.find_pcode_by_name.return_value = "B0000001"
    mock_graph.get_node.return_value = None
    node = make_retrieve_node(mock_builder, mock_graph)
    result = node(_state([
        _sub_query("", "law:direct_lookup", "民法", "第 9999 條")
    ]))

    assert result["documents"] == []


def test_direct_lookup_law_node_skipped(
    mock_builder: MagicMock, mock_graph: MagicMock
) -> None:
    mock_graph.find_pcode_by_name.return_value = "B0000001"
    mock_graph.get_node.return_value = {
        "type": "law",
        "law_name": "民法",
        "law_level": "法律",
        "law_category": "民事",
        "law_effective_date": "",
        "law_abandon_note": "",
        "source_pcode": "B0000001",
        "source_article_no": "",
        "source_paragraph": "",
        "law_modified_date": "20210101",
        "created_at": "2026-05-30T00:00:00+00:00",
    }
    node = make_retrieve_node(mock_builder, mock_graph)
    result = node(_state([
        _sub_query("", "law:direct_lookup", "民法", "B0000001")
    ]))

    assert result["documents"] == []


# ── law:graph_expand ──────────────────────────────────────────────────

def test_graph_expand_includes_original_and_cited(
    mock_builder: MagicMock, mock_graph: MagicMock
) -> None:
    mock_builder.search.return_value = [
        _chunk_result("B0000001", "第 184 條")
    ]
    mock_graph.get_cited_with_edges.return_value = [
        ("B0000001#第 185 條", {}),
    ]
    mock_graph.get_node.return_value = _article_node(
        "B0000001", "第 185 條"
    )
    node = make_retrieve_node(mock_builder, mock_graph)
    result = node(_state([_sub_query("侵權行為", "law:graph_expand")]))

    docs = result["documents"]
    node_ids = {d.metadata["node_id"] for d in docs}
    assert "B0000001#第 184 條" in node_ids
    assert "B0000001#第 185 條" in node_ids


def test_graph_expand_expand_k_limits_citations(
    mock_builder: MagicMock, mock_graph: MagicMock
) -> None:
    mock_builder.search.return_value = [
        _chunk_result("B0000001", "第 184 條")
    ]
    mock_graph.get_cited_with_edges.return_value = [
        (f"B0000001#第 {i} 條", {}) for i in range(10)
    ]
    mock_graph.get_node.return_value = _article_node()
    node = make_retrieve_node(mock_builder, mock_graph)
    result = node(_state([_sub_query("test", "law:graph_expand")]))

    # 原始 1 筆 + 最多 _EXPAND_K=3 筆引用
    assert len(result["documents"]) <= 4


# ── judgment:tavily（placeholder）────────────────────────────────────

def test_judgment_tavily_returns_no_documents(
    mock_builder: MagicMock, mock_graph: MagicMock
) -> None:
    node = make_retrieve_node(mock_builder, mock_graph)
    result = node(_state([
        _sub_query("侵權判決", "judgment:tavily")
    ]))

    assert result["documents"] == []
    mock_builder.search.assert_not_called()


# ── 去重 ──────────────────────────────────────────────────────────────

def test_deduplication_across_sub_queries(
    mock_builder: MagicMock, mock_graph: MagicMock
) -> None:
    same_result = _chunk_result("B0000001", "第 184 條")
    mock_builder.search.return_value = [same_result]
    node = make_retrieve_node(mock_builder, mock_graph)
    result = node(_state([
        _sub_query("q1", "law:semantic"),
        _sub_query("q2", "law:hyde"),
    ]))

    assert len(result["documents"]) == 1
