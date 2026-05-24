from typing import Protocol


class EdgeAttrsProtocol(Protocol):
    """所有邊屬性 TypedDict 必須包含的通用欄位介面。"""

    source_pcode: str
    source_article_no: str
    source_paragraph: str
    law_modified_date: str
    created_at: str
