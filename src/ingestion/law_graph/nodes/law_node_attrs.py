from typing import TypedDict


class LawNodeAttrs(TypedDict):
    type: str
    law_name: str
    law_level: str
    law_category: str
    law_effective_date: str
    law_abandon_note: str
    source_pcode: str
    source_article_no: str
    source_paragraph: str
    law_modified_date: str
    created_at: str
