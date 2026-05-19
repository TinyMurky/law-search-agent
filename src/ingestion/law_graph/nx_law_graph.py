import networkx as nx


class NxLawGraph:
    """以 NetworkX DiGraph 實作的法規圖查詢物件。

    節點：
      - 法律節點：ID = pcode，屬性 type="law"
      - 條文節點：ID = "{pcode}#{ArticleNo}"，屬性 type="article"

    邊：
      - law → article：relation="contains"
      - article → article：relation="cites"
    """

    def __init__(self, G: nx.DiGraph) -> None:
        self._G = G

    def get_cited_articles(
        self, pcode: str, article_no: str
    ) -> list[str]:
        """回傳此條文引用的所有條文（cites 邊的終點）。"""
        node_id = f"{pcode}#{article_no}"
        if node_id not in self._G:
            return []
        return list(self._G.successors(node_id))

    def get_citing_articles(
        self, pcode: str, article_no: str
    ) -> list[str]:
        """回傳引用此條文的所有條文（cites 邊的起點）。"""
        node_id = f"{pcode}#{article_no}"
        if node_id not in self._G:
            return []
        return [
            u
            for u, _, data in self._G.in_edges(node_id, data=True)
            if data.get("relation") == "cites"
        ]

    def get_law_articles(self, pcode: str) -> list[str]:
        """回傳某部法律的所有條文節點 ID（contains 邊的終點）。"""
        if pcode not in self._G:
            return []
        return list(self._G.successors(pcode))
