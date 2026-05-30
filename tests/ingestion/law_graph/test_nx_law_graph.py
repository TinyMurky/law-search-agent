import networkx as nx
import pytest

from ingestion.law_graph.edges import CitesEdgeAttrs, ContainsEdgeAttrs
from ingestion.law_graph.nodes import ArticleNodeAttrs, LawNodeAttrs
from ingestion.law_graph.nx_law_graph import NxLawGraph


@pytest.fixture
def graph() -> NxLawGraph:
    G: nx.DiGraph = nx.DiGraph()
    G.add_node("B0000001", type="law", law_name="民法")
    G.add_node("B0000001#第 1 條", type="article")
    G.add_node("B0000001#第 2 條", type="article")
    G.add_node("B0000001#第 3 條", type="article")
    G.add_edge("B0000001", "B0000001#第 1 條", relation="contains")
    G.add_edge("B0000001", "B0000001#第 2 條", relation="contains")
    G.add_edge("B0000001", "B0000001#第 3 條", relation="contains")
    G.add_edge(
        "B0000001#第 1 條", "B0000001#第 2 條", relation="cites"
    )
    G.add_edge(
        "B0000001#第 3 條", "B0000001#第 2 條", relation="cites"
    )
    return NxLawGraph(G)


# --- get_related ---

def test_get_related_out(graph: NxLawGraph) -> None:
    result = graph.get_related("B0000001#第 1 條", "cites", "out")
    assert result == ["B0000001#第 2 條"]


def test_get_related_in(graph: NxLawGraph) -> None:
    result = graph.get_related("B0000001#第 2 條", "cites", "in")
    assert set(result) == {
        "B0000001#第 1 條",
        "B0000001#第 3 條",
    }


def test_get_related_wrong_relation(graph: NxLawGraph) -> None:
    result = graph.get_related(
        "B0000001#第 1 條", "contains", "out"
    )
    assert result == []


def test_get_related_node_not_exist(graph: NxLawGraph) -> None:
    assert graph.get_related("X0000000", "cites", "out") == []


# --- 便利方法（內部呼叫 get_related）---

def test_get_cited_articles(graph: NxLawGraph) -> None:
    cited = graph.get_cited_articles("B0000001", "第 1 條")
    assert cited == ["B0000001#第 2 條"]


def test_get_cited_articles_empty(graph: NxLawGraph) -> None:
    cited = graph.get_cited_articles("B0000001", "第 2 條")
    assert cited == []


def test_get_citing_articles(graph: NxLawGraph) -> None:
    citing = graph.get_citing_articles("B0000001", "第 2 條")
    assert set(citing) == {
        "B0000001#第 1 條",
        "B0000001#第 3 條",
    }


def test_get_law_articles(graph: NxLawGraph) -> None:
    articles = graph.get_law_articles("B0000001")
    assert set(articles) == {
        "B0000001#第 1 條",
        "B0000001#第 2 條",
        "B0000001#第 3 條",
    }


def test_get_cited_articles_node_not_exist(
    graph: NxLawGraph,
) -> None:
    assert graph.get_cited_articles("X0000000", "第 1 條") == []


def test_get_citing_articles_node_not_exist(
    graph: NxLawGraph,
) -> None:
    assert graph.get_citing_articles("X0000000", "第 1 條") == []


def test_get_law_articles_node_not_exist(
    graph: NxLawGraph,
) -> None:
    assert graph.get_law_articles("X0000000") == []


# --- get_node / get_edge fixture（含完整屬性）---

_LAW_ATTRS: LawNodeAttrs = {
    "type": "law",
    "law_name": "民法",
    "law_level": "法律",
    "law_category": "民事",
    "law_effective_date": "19290510",
    "law_abandon_note": "",
    "source_pcode": "B0000001",
    "source_article_no": "",
    "source_paragraph": "",
    "law_modified_date": "20210101",
    "created_at": "2026-05-30T00:00:00+00:00",
}

_ARTICLE_ATTRS: ArticleNodeAttrs = {
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

_CONTAINS_ATTRS: ContainsEdgeAttrs = {
    "relation": "contains",
    "source_pcode": "B0000001",
    "source_article_no": "",
    "source_paragraph": "",
    "law_modified_date": "20210101",
    "created_at": "2026-05-30T00:00:00+00:00",
}

_CITES_ATTRS: CitesEdgeAttrs = {
    "relation": "cites",
    "citation_type": "bare",
    "source_pcode": "B0000001",
    "source_article_no": "第 184 條",
    "source_paragraph": "",
    "law_modified_date": "20210101",
    "created_at": "2026-05-30T00:00:00+00:00",
}


@pytest.fixture
def graph_with_attrs() -> NxLawGraph:
    G: nx.DiGraph = nx.DiGraph()
    G.add_node("B0000001", **_LAW_ATTRS)
    G.add_node("B0000001#第 184 條", **_ARTICLE_ATTRS)
    G.add_node("B0000001#第 185 條", **_ARTICLE_ATTRS)
    G.add_edge("B0000001", "B0000001#第 184 條", **_CONTAINS_ATTRS)
    G.add_edge(
        "B0000001#第 184 條", "B0000001#第 185 條", **_CITES_ATTRS
    )
    return NxLawGraph(G)


# --- get_node ---

def test_get_node_returns_law_attrs(
    graph_with_attrs: NxLawGraph,
) -> None:
    result = graph_with_attrs.get_node("B0000001")
    assert result is not None
    assert result["type"] == "law"
    assert result["law_name"] == "民法"
    assert result["law_level"] == "法律"
    assert result["source_pcode"] == "B0000001"


def test_get_node_returns_article_attrs(
    graph_with_attrs: NxLawGraph,
) -> None:
    result = graph_with_attrs.get_node("B0000001#第 184 條")
    assert result is not None
    assert result["type"] == "article"
    assert result["article_no"] == "第 184 條"  # type: ignore[typeddict-item]
    assert result["content"] != ""  # type: ignore[typeddict-item]


def test_get_node_not_found_returns_none(
    graph_with_attrs: NxLawGraph,
) -> None:
    assert graph_with_attrs.get_node("X0000000") is None


# --- get_edge ---

def test_get_edge_returns_contains_attrs(
    graph_with_attrs: NxLawGraph,
) -> None:
    result = graph_with_attrs.get_edge(
        "B0000001", "B0000001#第 184 條"
    )
    assert result is not None
    assert result["relation"] == "contains"
    assert result["source_pcode"] == "B0000001"
    assert result["source_article_no"] == ""


def test_get_edge_returns_cites_attrs(
    graph_with_attrs: NxLawGraph,
) -> None:
    result = graph_with_attrs.get_edge(
        "B0000001#第 184 條", "B0000001#第 185 條"
    )
    assert result is not None
    assert result["relation"] == "cites"
    assert result["citation_type"] == "bare"  # type: ignore[typeddict-item]
    assert result["source_article_no"] == "第 184 條"


def test_get_edge_not_found_returns_none(
    graph_with_attrs: NxLawGraph,
) -> None:
    assert graph_with_attrs.get_edge("X0000000", "Y0000000") is None


def test_get_edge_reversed_direction_returns_none(
    graph_with_attrs: NxLawGraph,
) -> None:
    # DiGraph 方向性：(法律 → 條文) 存在，反向不存在
    assert graph_with_attrs.get_edge(
        "B0000001#第 184 條", "B0000001"
    ) is None


# --- get_neighbors_with_edges ---

def test_get_neighbors_with_edges_out_returns_neighbor_and_edge(
    graph_with_attrs: NxLawGraph,
) -> None:
    result = graph_with_attrs.get_neighbors_with_edges(
        "B0000001#第 184 條", "cites", "out"
    )
    assert len(result) == 1
    neighbor_id, edge = result[0]
    assert neighbor_id == "B0000001#第 185 條"
    assert edge["relation"] == "cites"
    assert edge["citation_type"] == "bare"  # type: ignore[typeddict-item]


def test_get_neighbors_with_edges_in_returns_neighbor_and_edge(
    graph_with_attrs: NxLawGraph,
) -> None:
    result = graph_with_attrs.get_neighbors_with_edges(
        "B0000001#第 185 條", "cites", "in"
    )
    assert len(result) == 1
    neighbor_id, edge = result[0]
    assert neighbor_id == "B0000001#第 184 條"
    assert edge["relation"] == "cites"


def test_get_neighbors_with_edges_contains_out(
    graph_with_attrs: NxLawGraph,
) -> None:
    result = graph_with_attrs.get_neighbors_with_edges(
        "B0000001", "contains", "out"
    )
    neighbor_ids = [nid for nid, _ in result]
    assert "B0000001#第 184 條" in neighbor_ids
    edges = [e for _, e in result]
    assert all(e["relation"] == "contains" for e in edges)


def test_get_neighbors_with_edges_wrong_relation_returns_empty(
    graph_with_attrs: NxLawGraph,
) -> None:
    # 條文節點沒有 contains 出邊
    result = graph_with_attrs.get_neighbors_with_edges(
        "B0000001#第 184 條", "contains", "out"
    )
    assert result == []


def test_get_neighbors_with_edges_node_not_found_returns_empty(
    graph_with_attrs: NxLawGraph,
) -> None:
    assert graph_with_attrs.get_neighbors_with_edges(
        "X0000000", "cites", "out"
    ) == []


def test_get_neighbors_with_edges_no_incoming_cites_returns_empty(
    graph_with_attrs: NxLawGraph,
) -> None:
    # 第 184 條沒有被任何條文引用（入邊）
    result = graph_with_attrs.get_neighbors_with_edges(
        "B0000001#第 184 條", "cites", "in"
    )
    assert result == []


# --- get_cited_with_edges ---

def test_get_cited_with_edges_returns_neighbor_and_cites_edge(
    graph_with_attrs: NxLawGraph,
) -> None:
    result = graph_with_attrs.get_cited_with_edges(
        "B0000001", "第 184 條"
    )
    assert len(result) == 1
    neighbor_id, edge = result[0]
    assert neighbor_id == "B0000001#第 185 條"
    assert edge["relation"] == "cites"
    assert edge["citation_type"] == "bare"


def test_get_cited_with_edges_no_cites_returns_empty(
    graph_with_attrs: NxLawGraph,
) -> None:
    result = graph_with_attrs.get_cited_with_edges(
        "B0000001", "第 185 條"
    )
    assert result == []


def test_get_cited_with_edges_node_not_found_returns_empty(
    graph_with_attrs: NxLawGraph,
) -> None:
    assert graph_with_attrs.get_cited_with_edges(
        "X0000000", "第 1 條"
    ) == []


# --- get_citing_with_edges ---

def test_get_citing_with_edges_returns_neighbor_and_cites_edge(
    graph_with_attrs: NxLawGraph,
) -> None:
    result = graph_with_attrs.get_citing_with_edges(
        "B0000001", "第 185 條"
    )
    assert len(result) == 1
    neighbor_id, edge = result[0]
    assert neighbor_id == "B0000001#第 184 條"
    assert edge["relation"] == "cites"
    assert edge["citation_type"] == "bare"


def test_get_citing_with_edges_no_citing_returns_empty(
    graph_with_attrs: NxLawGraph,
) -> None:
    result = graph_with_attrs.get_citing_with_edges(
        "B0000001", "第 184 條"
    )
    assert result == []


def test_get_citing_with_edges_node_not_found_returns_empty(
    graph_with_attrs: NxLawGraph,
) -> None:
    assert graph_with_attrs.get_citing_with_edges(
        "X0000000", "第 1 條"
    ) == []
