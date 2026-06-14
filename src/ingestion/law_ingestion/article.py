from pydantic import BaseModel, ConfigDict, Field

from .citation_types import CitationType


class Article(BaseModel):
    """單一法規條文，對應 Law.LawArticles 陣列內的一筆資料。

    pcode 與 law_name 不存在於原始 JSON，由父 Law 的 model_validator 在解析時自動寫入。
    cited_articles 由 CitationExtractor 以 regex 解析條文內容後填入。
    """

    model_config = ConfigDict(populate_by_name=True)

    pcode: str = ""
    """所屬法規唯一識別碼，例如 A0000001，由父 Law 的 model_validator 寫入"""

    law_name: str = ""
    """所屬法規名稱，由父 Law 的 model_validator 寫入"""

    article_type: str = Field(alias="ArticleType")
    """條文型態：「A」為條文內容，「C」為章節標題"""

    article_no: str = Field(alias="ArticleNo", default="")
    """條號，例如「第 1 條」；章節標題（ArticleType=C）此欄位為空字串"""

    artical_content: str = Field(alias="ArticleContent")
    """條文內容"""

    cited_articles: list[tuple[str, CitationType]] = Field(
        default_factory=list,
    )
    """本條文引用的其他條文，格式為 (「{pcode}#{條號}」, CitationType)"""
