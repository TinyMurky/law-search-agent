import networkx as nx

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

    def _add_law(self, G: nx.DiGraph, law: Law) -> None:
        G.add_node(
            law.pcode,
            type="law",
            law_name=law.law_name,
            law_level=law.law_level,
        )
        for article in law.articles:
            if article.article_type != "A":
                continue
            node_id = f"{article.pcode}#{article.article_no}"
            G.add_node(
                node_id,
                type="article",
                law_name=article.law_name,
                article_no=article.article_no,
                content=article.artical_content,
            )
            G.add_edge(law.pcode, node_id, relation="contains")
            for cited in article.cited_articles:
                G.add_edge(node_id, cited, relation="cites")
