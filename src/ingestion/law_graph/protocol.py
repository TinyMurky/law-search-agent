from typing import Protocol


class LawGraphProtocol(Protocol):
    """法規圖查詢介面，NetworkX 與 Neo4j 實作均需符合此介面。"""

    def get_cited_articles(
        self, pcode: str, article_no: str
    ) -> list[str]:
        """回傳此條文引用的所有條文，格式為 {pcode}#{ArticleNo}。"""
        ...

    def get_citing_articles(
        self, pcode: str, article_no: str
    ) -> list[str]:
        """回傳引用此條文的所有條文，格式為 {pcode}#{ArticleNo}。"""
        ...

    def get_law_articles(self, pcode: str) -> list[str]:
        """回傳某部法律的所有條文節點 ID。"""
        ...
