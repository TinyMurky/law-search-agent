import pytest

from ingestion.law_ingestion.law import Law
from ingestion.law_graph.builder import LawGraphBuilder
from ingestion.law_graph.nx_law_graph import NxLawGraph


@pytest.fixture
def civil_law() -> Law:
    return Law.model_validate({
        "LawLevel": "法律",
        "LawName": "民法",
        "LawURL": (
            "https://law.moj.gov.tw/LawClass/"
            "LawAll.aspx?pcode=B0000001"
        ),
        "LawCategory": "民事",
        "LawModifiedDate": "20240101",
        "LawAttachements": [],
        "LawArticles": [
            {
                "ArticleType": "C",
                "ArticleNo": "",
                "ArticleContent": "第 一 章 總則",
            },
            {
                "ArticleType": "A",
                "ArticleNo": "第 1 條",
                "ArticleContent": "民事，法律所未規定者，依習慣。",
            },
            {
                "ArticleType": "A",
                "ArticleNo": "第 2 條",
                "ArticleContent": "民事所適用之習慣，以不背於公共秩序。",
            },
        ],
    })


@pytest.fixture
def graph(civil_law: Law) -> NxLawGraph:
    return LawGraphBuilder().build([civil_law])


def test_build_returns_nx_law_graph(civil_law: Law) -> None:
    result = LawGraphBuilder().build([civil_law])
    assert isinstance(result, NxLawGraph)


def test_law_node_created(graph: NxLawGraph) -> None:
    articles = graph.get_law_articles("B0000001")
    assert len(articles) == 2


def test_chapter_node_excluded(graph: NxLawGraph) -> None:
    articles = graph.get_law_articles("B0000001")
    for node_id in articles:
        assert "第 1 條" in node_id or "第 2 條" in node_id


def test_cites_edge_created() -> None:
    law = Law.model_validate({
        "LawLevel": "法律",
        "LawName": "民法",
        "LawURL": (
            "https://law.moj.gov.tw/LawClass/"
            "LawAll.aspx?pcode=B0000001"
        ),
        "LawCategory": "民事",
        "LawModifiedDate": "20240101",
        "LawAttachements": [],
        "LawArticles": [
            {
                "ArticleType": "A",
                "ArticleNo": "第 1 條",
                "ArticleContent": "依第二條規定。",
            },
        ],
    })
    law.articles[0].cited_articles = ["B0000001#第 2 條"]
    g = LawGraphBuilder().build([law])
    cited = g.get_cited_articles("B0000001", "第 1 條")
    assert "B0000001#第 2 條" in cited


def test_empty_laws() -> None:
    g = LawGraphBuilder().build([])
    assert g.get_law_articles("B0000001") == []
