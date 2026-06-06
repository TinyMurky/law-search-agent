from unittest.mock import MagicMock

import pytest

from agent.tools.law import make_law_tools


@pytest.fixture
def mock_builder() -> MagicMock:
    builder = MagicMock()
    builder.search.return_value = [
        {
            "node_id": "B0000001#第 184 條",
            "law_name": "民法",
            "article_no": "第 184 條",
            "content": "因故意或過失，不法侵害他人之權利者，負損害賠償責任。",
            "score": 0.9,
        }
    ]
    return builder


@pytest.fixture
def mock_graph() -> MagicMock:
    graph = MagicMock()
    graph.get_cited_with_edges.return_value = [
        (
            "B0000001#第 185 條",
            {
                "relation": "cites",
                "citation_type": "bare",
                "source_pcode": "B0000001",
                "source_article_no": "第 184 條",
                "source_paragraph": "",
                "law_modified_date": "20210101",
                "created_at": "2026-05-30T00:00:00+00:00",
            },
        )
    ]
    graph.get_citing_with_edges.return_value = []
    graph.get_node.return_value = {
        "type": "article",
        "pcode": "B0000001",
        "law_name": "民法",
        "article_no": "第 185 條",
        "content": "數人共同不法侵害他人之權利者，連帶負損害賠償責任。",
        "source_pcode": "B0000001",
        "source_article_no": "第 185 條",
        "source_paragraph": "",
        "law_modified_date": "20210101",
        "created_at": "2026-05-30T00:00:00+00:00",
    }
    graph.get_law_articles.return_value = [
        "B0000001#第 1 條",
        "B0000001#第 2 條",
        "B0000001#第 3 條",
    ]
    return graph


# --- search_law_articles ---

def test_search_law_articles_formats_results(
    mock_builder: MagicMock, mock_graph: MagicMock
) -> None:
    tools = make_law_tools(mock_builder, mock_graph)
    search = next(t for t in tools if t.name == "search_law_articles")
    result = search.invoke({"query": "侵權行為"})
    assert "民法" in result
    assert "第 184 條" in result
    assert "因故意或過失" in result


def test_search_law_articles_empty_returns_message(
    mock_builder: MagicMock, mock_graph: MagicMock
) -> None:
    mock_builder.search.return_value = []
    tools = make_law_tools(mock_builder, mock_graph)
    search = next(t for t in tools if t.name == "search_law_articles")
    result = search.invoke({"query": "不存在的查詢"})
    assert "找不到" in result


def test_search_law_articles_multiple_results_separated(
    mock_builder: MagicMock, mock_graph: MagicMock
) -> None:
    mock_builder.search.return_value = [
        {
            "node_id": "B0000001#第 184 條",
            "law_name": "民法",
            "article_no": "第 184 條",
            "content": "內容A",
            "score": 0.9,
        },
        {
            "node_id": "B0000001#第 185 條",
            "law_name": "民法",
            "article_no": "第 185 條",
            "content": "內容B",
            "score": 0.8,
        },
    ]
    tools = make_law_tools(mock_builder, mock_graph)
    search = next(t for t in tools if t.name == "search_law_articles")
    result = search.invoke({"query": "侵權"})
    assert "內容A" in result
    assert "內容B" in result
    assert "---" in result


# --- get_related_articles ---

def test_get_related_articles_shows_cited(
    mock_builder: MagicMock, mock_graph: MagicMock
) -> None:
    tools = make_law_tools(mock_builder, mock_graph)
    get_rel = next(
        t for t in tools if t.name == "get_related_articles"
    )
    result = get_rel.invoke(
        {"pcode": "B0000001", "article_no": "第 184 條"}
    )
    assert "第 185 條" in result
    assert "bare" in result
    assert "數人共同" in result


def test_get_related_articles_no_relations_returns_message(
    mock_builder: MagicMock, mock_graph: MagicMock
) -> None:
    mock_graph.get_cited_with_edges.return_value = []
    mock_graph.get_citing_with_edges.return_value = []
    tools = make_law_tools(mock_builder, mock_graph)
    get_rel = next(
        t for t in tools if t.name == "get_related_articles"
    )
    result = get_rel.invoke(
        {"pcode": "B0000001", "article_no": "第 1 條"}
    )
    assert "無引用關係" in result


def test_get_related_articles_shows_citing(
    mock_builder: MagicMock, mock_graph: MagicMock
) -> None:
    mock_graph.get_cited_with_edges.return_value = []
    mock_graph.get_citing_with_edges.return_value = [
        (
            "B0000001#第 183 條",
            {
                "relation": "cites",
                "citation_type": "bare",
                "source_pcode": "B0000001",
                "source_article_no": "第 183 條",
                "source_paragraph": "",
                "law_modified_date": "20210101",
                "created_at": "2026-05-30T00:00:00+00:00",
            },
        )
    ]
    tools = make_law_tools(mock_builder, mock_graph)
    get_rel = next(
        t for t in tools if t.name == "get_related_articles"
    )
    result = get_rel.invoke(
        {"pcode": "B0000001", "article_no": "第 184 條"}
    )
    assert "第 183 條" in result
    assert "引用此條" in result


# --- get_law_articles ---

def test_get_law_articles_returns_article_ids(
    mock_builder: MagicMock, mock_graph: MagicMock
) -> None:
    tools = make_law_tools(mock_builder, mock_graph)
    get_arts = next(
        t for t in tools if t.name == "get_law_articles"
    )
    result = get_arts.invoke({"pcode": "B0000001"})
    assert "B0000001#第 1 條" in result
    assert "B0000001#第 2 條" in result


def test_get_law_articles_empty_returns_message(
    mock_builder: MagicMock, mock_graph: MagicMock
) -> None:
    mock_graph.get_law_articles.return_value = []
    tools = make_law_tools(mock_builder, mock_graph)
    get_arts = next(
        t for t in tools if t.name == "get_law_articles"
    )
    result = get_arts.invoke({"pcode": "X0000000"})
    assert "找不到" in result


# --- get_article ---

def test_get_article_returns_content(
    mock_builder: MagicMock, mock_graph: MagicMock
) -> None:
    mock_graph.get_node.return_value = {
        "type": "article",
        "pcode": "B0000001",
        "law_name": "民法",
        "article_no": "第 184 條",
        "content": "因故意或過失，不法侵害他人之權利者，負損害賠償責任。",
        "source_pcode": "B0000001",
        "source_article_no": "第 184 條",
        "source_paragraph": "",
        "law_modified_date": "20210101",
        "created_at": "2026-05-30T00:00:00+00:00",
    }
    tools = make_law_tools(mock_builder, mock_graph)
    get_art = next(t for t in tools if t.name == "get_article")
    result = get_art.invoke({"pcode": "B0000001", "article_no": "第 184 條"})
    assert "民法" in result
    assert "第 184 條" in result
    assert "因故意或過失" in result
    mock_graph.get_node.assert_called_with("B0000001#第 184 條")


def test_get_article_not_found_returns_message(
    mock_builder: MagicMock, mock_graph: MagicMock
) -> None:
    mock_graph.get_node.return_value = None
    tools = make_law_tools(mock_builder, mock_graph)
    get_art = next(t for t in tools if t.name == "get_article")
    result = get_art.invoke({"pcode": "X0000000", "article_no": "第 1 條"})
    assert "找不到" in result
    assert "X0000000#第 1 條" in result


def test_get_article_law_node_returns_not_found(
    mock_builder: MagicMock, mock_graph: MagicMock
) -> None:
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
    tools = make_law_tools(mock_builder, mock_graph)
    get_art = next(t for t in tools if t.name == "get_article")
    result = get_art.invoke({"pcode": "B0000001", "article_no": "B0000001"})
    assert "找不到" in result
