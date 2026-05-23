from datetime import datetime, timezone

import networkx as nx

from ingestion.law_ingestion.article import Article
from ingestion.law_ingestion.law import Law

from .nx_law_graph import NxLawGraph


class LawGraphBuilder:
    """將 list[Law] 建成 NxLawGraph。

    需在 CitationExtractor 跑完後呼叫，
    確保 Article.cited_articles 已填好。
    """

    def build(self, laws: list[Law]) -> NxLawGraph:
        G: nx.DiGraph = nx.DiGraph()
        for law in laws:
            self._add_law(G, law)
        return NxLawGraph(G)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def _add_law(self, G: nx.DiGraph, law: Law) -> None:
        G.add_node(
            law.pcode,
            type="law",
            law_name=law.law_name,
            law_level=law.law_level,
            law_category=law.law_category,
            law_effective_date=law.law_effective_date,
            law_abandon_note=law.law_abandon_note,
            source_pcode=law.pcode,
            source_article_no="",
            source_paragraph="",
            law_modified_date=law.law_modified_date,
            created_at=self._now(),
        )
        for article in law.articles:
            if article.article_type != "A":
                continue
            self._add_article(G, law, article)

    def _add_article(
        self, G: nx.DiGraph, law: Law, article: Article
    ) -> None:
        node_id = f"{article.pcode}#{article.article_no}"
        G.add_node(
            node_id,
            type="article",
            pcode=article.pcode,
            law_name=article.law_name,
            article_no=article.article_no,
            content=article.artical_content,
            source_pcode=article.pcode,
            source_article_no=article.article_no,
            source_paragraph="",
            law_modified_date=law.law_modified_date,
            created_at=self._now(),
        )
        G.add_edge(law.pcode, node_id, relation="contains")
        for cited in article.cited_articles:
            G.add_edge(node_id, cited, relation="cites")
