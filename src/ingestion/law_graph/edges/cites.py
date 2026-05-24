from typing import TypedDict

from ingestion.law_ingestion.citation_types import CitationType


class CitesEdgeAttrs(TypedDict):
    relation: str
    citation_type: CitationType
    source_pcode: str
    source_article_no: str
    source_paragraph: str
    law_modified_date: str
    created_at: str
