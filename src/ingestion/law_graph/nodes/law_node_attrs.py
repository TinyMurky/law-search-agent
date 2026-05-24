from typing import TypedDict


class LawNodeAttrs(TypedDict):
    """Law 節點的屬性，對應全國法規資料庫的一部法律。"""

    type: str  # 固定為 "law"
    law_name: str  # 法律名稱，例如「民法」
    law_level: str  # 法規位階，例如「憲法」、「法律」
    law_category: str  # 法規類別，例如「民事」、「刑事」
    law_effective_date: str  # 施行日期，格式 "YYYYMMDD"；未定則為 ""
    law_abandon_note: str  # 廢止備註；未廢止則為 ""
    source_pcode: str  # 來源法律 pcode，Law 節點填自身 pcode
    source_article_no: str  # 來源條文；Law 節點固定填 ""
    source_paragraph: str  # 來源項次；固定填 ""
    law_modified_date: str  # 法律最後修正日期，格式 "YYYYMMDD"
    created_at: str  # 建圖時間，ISO 8601 UTC，例如 "2026-05-24T…"
