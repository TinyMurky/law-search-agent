from typing import cast

import networkx as nx

from .edges import CitesEdgeAttrs, ContainsEdgeAttrs
from .nodes import ArticleNodeAttrs, LawNodeAttrs
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
        return [
            nid for nid, _ in self.get_cited_with_edges(pcode, article_no)
        ]

    def get_citing_articles(
        self, pcode: str, article_no: str
    ) -> list[str]:
        """回傳引用此條文的所有條文（cites 入邊）。"""
        return [
            nid for nid, _ in self.get_citing_with_edges(pcode, article_no)
        ]

    def get_law_articles(self, pcode: str) -> list[str]:
        """回傳某部法律的所有條文節點 ID（contains 出邊）。"""
        return self.get_related(pcode, "contains", "out")

    def get_node(
        self, node_id: str
    ) -> LawNodeAttrs | ArticleNodeAttrs | None:
        """以 node_id 取出節點屬性，不存在回傳 None。"""
        if node_id not in self._G:
            return None
        raw = self._G.nodes[node_id]
        if raw.get("type") == "law":
            return cast(LawNodeAttrs, raw)
        return cast(ArticleNodeAttrs, raw)

    def get_edge(
        self, u: str, v: str
    ) -> ContainsEdgeAttrs | CitesEdgeAttrs | None:
        """取出兩節點之間的邊屬性，不存在回傳 None。"""
        if not self._G.has_edge(u, v):
            return None
        raw = self._G.edges[u, v]
        if raw.get("relation") == "contains":
            return cast(ContainsEdgeAttrs, raw)
        return cast(CitesEdgeAttrs, raw)

    def get_neighbors_with_edges(
        self,
        node_id: str,
        relation: str,
        direction: Direction = "out",
    ) -> list[tuple[str, ContainsEdgeAttrs | CitesEdgeAttrs]]:
        """回傳符合 relation 的 [(鄰居 node_id, 邊屬性), ...]。

        direction 控制邊的方向：
          "out" — node_id 發出的邊（node_id → 鄰居）
                  例：取條文引用的對象 → get_neighbors_with_edges(
                          id, "cites", "out")
          "in"  — 指向 node_id 的邊（鄰居 → node_id）
                  例：取引用此條文的來源 → get_neighbors_with_edges(
                          id, "cites", "in")
        """
        if node_id not in self._G:
            return []
        if direction == "out":
            return [
                (v, cast(ContainsEdgeAttrs | CitesEdgeAttrs, d))
                for _, v, d in self._G.out_edges(node_id, data=True)
                if d.get("relation") == relation
            ]
        return [
            (u, cast(ContainsEdgeAttrs | CitesEdgeAttrs, d))
            for u, _, d in self._G.in_edges(node_id, data=True)
            if d.get("relation") == relation
        ]

    def get_cited_with_edges(
        self, pcode: str, article_no: str
    ) -> list[tuple[str, CitesEdgeAttrs]]:
        """取條文引用的對象，連同邊屬性（含 citation_type）一起回傳。"""
        pairs = self.get_neighbors_with_edges(
            f"{pcode}#{article_no}", "cites", "out"
        )
        return [(nid, cast(CitesEdgeAttrs, e)) for nid, e in pairs]

    def get_citing_with_edges(
        self, pcode: str, article_no: str
    ) -> list[tuple[str, CitesEdgeAttrs]]:
        """取引用此條文的來源，連同邊屬性（含 citation_type）一起回傳。"""
        pairs = self.get_neighbors_with_edges(
            f"{pcode}#{article_no}", "cites", "in"
        )
        return [(nid, cast(CitesEdgeAttrs, e)) for nid, e in pairs]
