import networkx as nx

from .protocol import Direction


class NxLawGraph:
    """以 NetworkX DiGraph 實作的法規圖查詢物件。

    節點：
      - 法律節點：ID = pcode，屬性 type="law"
      - 條文節點：ID = "{pcode}#{ArticleNo}"，屬性 type="article"

    邊（relation 屬性）：
      - "contains"：law/division → article
      - "cites"   ：article → article
    """

    def __init__(self, G: nx.DiGraph) -> None:
        self._G = G

    def get_related(
        self,
        node_id: str,
        relation: str,
        direction: Direction = "out",
    ) -> list[str]:
        """通用關係查詢，以 relation 和方向過濾邊。"""
        if node_id not in self._G:
            return []
        if direction == "out":
            return [
                v
                for _, v, d in self._G.out_edges(node_id, data=True)
                if d.get("relation") == relation
            ]
        return [
            u
            for u, _, d in self._G.in_edges(node_id, data=True)
            if d.get("relation") == relation
        ]

    def get_cited_articles(
        self, pcode: str, article_no: str
    ) -> list[str]:
        """回傳此條文引用的所有條文（cites 出邊）。"""
        return self.get_related(
            f"{pcode}#{article_no}", "cites", "out"
        )

    def get_citing_articles(
        self, pcode: str, article_no: str
    ) -> list[str]:
        """回傳引用此條文的所有條文（cites 入邊）。"""
        return self.get_related(
            f"{pcode}#{article_no}", "cites", "in"
        )

    def get_law_articles(self, pcode: str) -> list[str]:
        """回傳某部法律的所有條文節點 ID（contains 出邊）。"""
        return self.get_related(pcode, "contains", "out")
