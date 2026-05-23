import networkx as nx
import pytest

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
