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
        """以既有的 NetworkX DiGraph 初始化查詢物件。

        Args:
            G (nx.DiGraph): 已建好的法規圖，節點與邊需符合本類別
                docstring 所述的結構。
        """
        self._G = G

        # 所有法規的正式名稱
        self._law_names: list[str] = []

    def get_related(
        self,
        node_id: str,
        relation: str,
        direction: Direction = "out",
    ) -> list[str]:
        """通用關係查詢，以 relation 和方向過濾邊。

        Args:
            node_id (str): 起點節點 ID。
            relation (str): 邊的 relation 屬性，例如 "cites"、
                "contains"。
            direction (Direction): "out" 取出邊鄰居，"in" 取入邊
                鄰居，預設為 "out"。

        Returns:
            list[str]: 符合 relation 與方向的鄰居節點 ID 清單，
                node_id 不存在時回傳空清單。
        """
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

    def get_cited_articles(self, pcode: str, article_no: str) -> list[str]:
        """回傳此條文引用的所有條文（cites 出邊）。

        Args:
            pcode (str): 條文所屬法律 pcode，例如 "B0000001"。
            article_no (str): 條號，例如 "第 184 條"。

        Returns:
            list[str]: 被引用的條文節點 ID 清單，無引用時回傳
                空清單。
        """
        return [nid for nid, _ in self.get_cited_with_edges(pcode, article_no)]

    def get_citing_articles(self, pcode: str, article_no: str) -> list[str]:
        """回傳引用此條文的所有條文（cites 入邊）。

        Args:
            pcode (str): 條文所屬法律 pcode，例如 "B0000001"。
            article_no (str): 條號，例如 "第 184 條"。

        Returns:
            list[str]: 引用此條文的條文節點 ID 清單，無引用時
                回傳空清單。
        """
        pairs = self.get_citing_with_edges(pcode, article_no)
        return [nid for nid, _ in pairs]

    def get_law_articles(self, pcode: str) -> list[str]:
        """回傳某部法律的所有條文節點 ID（contains 出邊）。

        Args:
            pcode (str): 法律唯一識別碼，例如 "B0000001"。

        Returns:
            list[str]: 該法律所有條文節點 ID 清單，pcode 不存在
                時回傳空清單。
        """
        return self.get_related(pcode, "contains", "out")

    def get_node(self, node_id: str) -> LawNodeAttrs | ArticleNodeAttrs | None:
        """以 node_id 取出節點屬性，不存在回傳 None。

        Args:
            node_id (str): 節點 ID，Law 為 pcode，
                Article 為 "{pcode}#{article_no}"。

        Returns:
            LawNodeAttrs | ArticleNodeAttrs | None:
                節點屬性，節點不存在時回傳 None。
        """
        if node_id not in self._G:
            return None
        raw = self._G.nodes[node_id]
        if raw.get("type") == "law":
            return cast(LawNodeAttrs, raw)
        return cast(ArticleNodeAttrs, raw)

    def get_law(self, pcode: str) -> LawNodeAttrs | None:
        """以 pcode 取出法律節點屬性。

        底層呼叫 get_node，確認 type="law" 後回傳正確型別。

        Args:
            pcode (str): 法律唯一識別碼，例如 "B0000001"。

        Returns:
            LawNodeAttrs | None: 法律節點屬性，不存在時回傳 None。
        """
        node = self.get_node(pcode)
        if node is None or node["type"] != "law":
            return None
        return cast(LawNodeAttrs, node)

    def get_all_law_names(self) -> list[str]:
        """回覆整本法規的各正式法律名稱。

        Returns:
            list[str]: 中華民國各法規的正式名稱。
        """
        if len(self._law_names) > 0:
            return self._law_names

        self._law_names = sorted(
            attrs["law_name"]
            for _, attrs in self._G.nodes(data=True)
            if attrs.get("type") == "law"
        )

        return self._law_names

    def get_article(
        self, pcode: str, article_no: str
    ) -> tuple[str, ArticleNodeAttrs] | None:
        """以 pcode 與 article_no 取出條文節點 ID 與屬性。

        底層呼叫 get_node，確認 type="article" 後回傳
        (node_id, attrs) tuple，讓呼叫端不必自行組合 node_id。

        Args:
            pcode (str): 所屬法律 pcode，例如 "B0000001"。
            article_no (str): 條號，例如 "第 184 條"。

        Returns:
            tuple[str, ArticleNodeAttrs] | None:
                (node_id, 條文節點屬性)，不存在時回傳 None。
        """
        node_id = f"{pcode}#{article_no}"
        node = self.get_node(node_id)
        if node is None or node["type"] != "article":
            return None
        return node_id, cast(ArticleNodeAttrs, node)

    def get_edge(
        self,
        u: str,
        v: str,
    ) -> ContainsEdgeAttrs | CitesEdgeAttrs | None:
        """取出兩節點之間的邊屬性，不存在回傳 None。

        Args:
            u (str): 邊的起點節點 ID。
            v (str): 邊的終點節點 ID。

        Returns:
            ContainsEdgeAttrs | CitesEdgeAttrs | None: 邊屬性，
                u 到 v 之間沒有邊時回傳 None。
        """
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

        Args:
            node_id (str): 起點節點 ID。
            relation (str): 邊的 relation 屬性，例如 "cites"、
                "contains"。
            direction (Direction): "out" 取出邊鄰居，"in" 取入邊
                鄰居，預設為 "out"。

        Returns:
            list[tuple[str, ContainsEdgeAttrs | CitesEdgeAttrs]]:
                [(鄰居節點 ID, 邊屬性), ...]，node_id 不存在或
                無符合的邊時回傳空清單。
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
        """取條文引用的對象，連同邊屬性（含 citation_type）一起回傳。

        Args:
            pcode (str): 條文所屬法律 pcode，例如 "B0000001"。
            article_no (str): 條號，例如 "第 184 條"。

        Returns:
            list[tuple[str, CitesEdgeAttrs]]: [(被引用條文節點
                ID (node_id), 邊屬性), ...]，無引用時回傳空清單。
        """
        pairs = self.get_neighbors_with_edges(
            f"{pcode}#{article_no}",
            "cites",
            "out",
        )
        return [(nid, cast(CitesEdgeAttrs, e)) for nid, e in pairs]

    def get_citing_with_edges(
        self, pcode: str, article_no: str
    ) -> list[tuple[str, CitesEdgeAttrs]]:
        """取引用此條文的來源，連同邊屬性（含 citation_type）一起回傳。

        Args:
            pcode (str): 條文所屬法律 pcode，例如 "B0000001"。
            article_no (str): 條號，例如 "第 184 條"。

        Returns:
            list[tuple[str, CitesEdgeAttrs]]: [(引用此條文的
                節點 ID, 邊屬性), ...]，無引用時回傳空清單。
        """
        pairs = self.get_neighbors_with_edges(
            f"{pcode}#{article_no}",
            "cites",
            "in",
        )
        return [(nid, cast(CitesEdgeAttrs, e)) for nid, e in pairs]

    def find_pcode_by_name(self, law_name: str) -> str | None:
        """依法律名稱查找 pcode，找不到回傳 None。

        Args:
            law_name (str): 法律名稱，例如「民法」。

        Returns:
            str | None: 對應的法律 pcode，找不到時回傳 None。
        """
        for node_id, attrs in self._G.nodes(data=True):
            is_law = attrs.get("type") == "law"
            same_name = attrs.get("law_name") == law_name
            if is_law and same_name:
                return str(node_id)
        return None

    def resolve_law_names(self, law_name: str) -> list[str]:
        """將口語化法律名稱解析為候選正統名稱清單。

        依序嘗試：完全相符 → 補「中華民國」前綴完全相符 →
        substring 篩選候選。回傳 0 筆代表完全找不到，1 筆代表
        唯一候選，2 筆以上代表名稱有歧義，呼叫端可視需要拆成
        多個查詢分別處理。

        Args:
            law_name (str): 使用者輸入或 LLM 解析出的法律名稱，
                可能是正統名稱或口語簡稱，例如「刑法」。

        Returns:
            list[str]: 候選的正統法律名稱清單。
        """
        if not law_name:
            return []

        all_names = self.get_all_law_names()
        if law_name in all_names:
            return [law_name]

        prefixed = f"中華民國{law_name}"
        if prefixed in all_names:
            return [prefixed]

        return [n for n in all_names if law_name in n]
