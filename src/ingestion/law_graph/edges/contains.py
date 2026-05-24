from typing import TypedDict


class ContainsEdgeAttrs(TypedDict):
    """CONTAINS 邊的屬性：Law/Division → Article。"""

    relation: str  # 固定為 "contains"
    source_pcode: str  # 發出此邊的 Law 節點 pcode
    source_article_no: str  # Law 節點發出，固定填 ""
    source_paragraph: str  # 固定填 ""
    law_modified_date: str  # 所屬法律最後修正日期，格式 "YYYYMMDD"
    created_at: str  # 建圖時間，ISO 8601 UTC，例如 "2026-05-24T…"
