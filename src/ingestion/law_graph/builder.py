from datetime import datetime, timezone

import networkx as nx

from ingestion.law_ingestion.article import Article
from ingestion.law_ingestion.law import Law

from .edges import CitesEdgeAttrs, ContainsEdgeAttrs
from .nodes import ArticleNodeAttrs, LawNodeAttrs
from .nx_law_graph import NxLawGraph


class LawGraphBuilder:
    """將 list[Law] 建成 NxLawGraph。

    需在 CitationExtractor 跑完後呼叫，
    確保 Article.cited_articles 已填好。
    """

    def build(self, laws: list[Law]) -> NxLawGraph:
        """將法律清單建成 NxLawGraph。

        Args:
            laws (list[Law]): 已由 CitationExtractor 填好
                cited_articles 的法律清單。

        Returns:
            NxLawGraph: 建立完成的法規圖查詢物件。
        """
        G: nx.DiGraph = nx.DiGraph()
        for law in laws:
            self._add_law(G, law)
        return NxLawGraph(G)

    @staticmethod
    def _now() -> str:
        """取得目前時間的 ISO 8601 UTC 字串。

        Returns:
            str: 建圖時間戳，例如 "2026-05-24T10:30:00+00:00"。
        """
        return datetime.now(timezone.utc).isoformat()

    def _add_law(self, G: nx.DiGraph, law: Law) -> None:
        """將單一法律與其條文加入圖中。

        Args:
            G (nx.DiGraph): 正在建立的圖。
            law (Law): 要加入的法律。
        """
        law_attrs: LawNodeAttrs = {
            "type": "law",
            "law_name": law.law_name,
            "law_level": law.law_level,
            "law_category": law.law_category,
            "law_effective_date": law.law_effective_date,
            "law_abandon_note": law.law_abandon_note,
            "source_pcode": law.pcode,
            "source_article_no": "",
            "source_paragraph": "",
            "law_modified_date": law.law_modified_date,
            "created_at": self._now(),
        }
        G.add_node(law.pcode, **law_attrs)
        for article in law.articles:
            if article.article_type != "A":
                continue
            self._add_article(G, law, article)

    def _add_article(
        self, G: nx.DiGraph, law: Law, article: Article
    ) -> None:
        """將單一條文節點、contains 邊與 cites 邊加入圖中。

        Args:
            G (nx.DiGraph): 正在建立的圖。
            law (Law): 條文所屬的法律。
            article (Article): 要加入的條文。
        """
        node_id = f"{article.pcode}#{article.article_no}"
        article_attrs: ArticleNodeAttrs = {
            "type": "article",
            "pcode": article.pcode,
            "law_name": article.law_name,
            "article_no": article.article_no,
            "content": article.artical_content,
            "source_pcode": article.pcode,
            "source_article_no": article.article_no,
            "source_paragraph": "",
            "law_modified_date": law.law_modified_date,
            "created_at": self._now(),
        }
        G.add_node(node_id, **article_attrs)
        contains_attrs: ContainsEdgeAttrs = {
            "relation": "contains",
            "source_pcode": law.pcode,
            "source_article_no": "",
            "source_paragraph": "",
            "law_modified_date": law.law_modified_date,
            "created_at": self._now(),
        }
        G.add_edge(law.pcode, node_id, **contains_attrs)
        for cited_id, citation_type in article.cited_articles:
            cites_attrs: CitesEdgeAttrs = {
                "relation": "cites",
                "citation_type": citation_type,
                "source_pcode": article.pcode,
                # 這邊需考慮 source_artical_no 到底是 引用者還是被引用者
                "source_article_no": article.article_no,
                "source_paragraph": "",
                "law_modified_date": law.law_modified_date,
                "created_at": self._now(),
            }
            G.add_edge(node_id, cited_id, **cites_attrs)
