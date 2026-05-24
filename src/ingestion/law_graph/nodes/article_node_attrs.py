from typing import TypedDict


class ArticleNodeAttrs(TypedDict):
    """Article 節點的屬性，對應一部法律內的單一條文。"""

    type: str  # 固定為 "article"
    pcode: str  # 所屬法律 pcode，例如 "B0000001"
    law_name: str  # 所屬法律名稱，例如「民法」
    article_no: str  # 條號，格式 "第 N 條"，例如 "第 184 條"
    content: str  # 條文全文
    source_pcode: str  # 來源法律 pcode，與 pcode 相同
    source_article_no: str  # 來源條文，與 article_no 相同
    source_paragraph: str  # 來源項次；固定填 ""
    law_modified_date: str  # 法律最後修正日期，格式 "YYYYMMDD"
    created_at: str  # 建圖時間，ISO 8601 UTC，例如 "2026-05-24T…"
