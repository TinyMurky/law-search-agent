from typing import Literal, Protocol

Direction = Literal["out", "in"]


class LawGraphProtocol(Protocol):
    """法規圖查詢介面，NetworkX 與 Neo4j 實作均需符合此介面。

    Protocol 只定義 get_related 一個方法，新增 edge type 時
    不需要修改此介面。各實作可自行提供語意化的便利方法。
    """

    def get_related(
        self,
        node_id: str,
        relation: str,
        direction: Direction = "out",
    ) -> list[str]:
        """通用關係查詢。

        Args:
            node_id:   起點節點 ID
            relation:  邊的 relation 屬性，e.g. "cites"、"contains"
            direction: "out" 查出邊終點；"in" 查入邊起點

        Returns:
            符合條件的鄰居節點 ID 清單
        """
        ...
