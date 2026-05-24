from typing import TypedDict

from ingestion.law_ingestion.citation_types import CitationType


class CitesEdgeAttrs(TypedDict):
    """CITES 邊的屬性：Article → Article（條文引用）。"""

    relation: str  # 固定為 "cites"
    citation_type: CitationType  # 引用型態，見 CitationType 定義
    source_pcode: str  # 引用來源的條文 pcode
    source_article_no: str  # 引用來源的條號，格式 "第 N 條"
    source_paragraph: str  # 來源項次；固定填 ""
    law_modified_date: str  # 來源法律最後修正日期，格式 "YYYYMMDD"
    created_at: str  # 建圖時間，ISO 8601 UTC，例如 "2026-05-24T…"
