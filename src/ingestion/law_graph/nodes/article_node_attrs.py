from typing import TypedDict


class ArticleNodeAttrs(TypedDict):
    type: str
    pcode: str
    law_name: str
    article_no: str
    content: str
    source_pcode: str
    source_article_no: str
    source_paragraph: str
    law_modified_date: str
    created_at: str
