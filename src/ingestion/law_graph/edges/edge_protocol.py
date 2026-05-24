from typing import Protocol


class EdgeAttrsProtocol(Protocol):
    """所有邊屬性 TypedDict 必須包含的通用欄位介面。"""

    source_pcode: str  # 來源法律 pcode
    source_article_no: str  # 來源條文；Law 節點發出的邊填 ""
    source_paragraph: str  # 來源項次；目前均填 ""
    law_modified_date: str  # 來源法律最後修正日期，格式 "YYYYMMDD"
    created_at: str  # 建圖時間，ISO 8601 UTC
