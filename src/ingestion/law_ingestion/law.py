from urllib.parse import parse_qs, urlparse

from pydantic import (BaseModel, ConfigDict, Field, computed_field,
                      model_validator)

from .article import Article


class LawAttachment(BaseModel):
    """法規附件，對應 Law.LawAttachements 陣列內的一筆資料"""

    model_config = ConfigDict(populate_by_name=True)

    file_name: str = Field(alias="FileName")
    """附件檔案名稱"""

    file_url: str = Field(alias="FileURL")
    """附件下載網址"""


class Law(BaseModel):
    """法規資料，對應全國法規資料庫 ChLaw.json 內 Laws 陣列的單一法規物件"""

    model_config = ConfigDict(populate_by_name=True)

    law_level: str = Field(alias="LawLevel")
    """法規位階，例如「憲法」、「法律」、「命令」"""

    law_name: str = Field(alias="LawName")
    """法規名稱"""

    law_url: str = Field(alias="LawURL")
    """法規於全國法規資料庫的網址，
    格式：https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=XXXXXXXX
    """

    law_category: str = Field(alias="LawCategory")
    """法規類別"""

    law_modified_date: str = Field(alias="LawModifiedDate", default="")
    """法規最後異動日期，格式為 YYYYMMDD"""

    law_effective_date: str = Field(alias="LawEffectiveDate", default="")
    """生效日期，格式為 YYYYMMDD"""

    law_effective_note: str = Field(alias="LawEffectiveNote", default="")
    """生效內容說明"""

    law_abandon_note: str = Field(alias="LawAbandonNote", default="")
    """廢止註記"""

    law_has_eng_version: str = Field(alias="LawHasEngVersion", default="")
    """是否有英譯版本，「Y」表示有"""

    eng_law_name: str = Field(alias="EngLawName", default="")
    """英文法規名稱"""

    law_attachments: list[LawAttachment] = Field(
        alias="LawAttachements", default_factory=list
    )
    """法規附件清單"""

    law_histories: str = Field(alias="LawHistories", default="")
    """沿革內容"""

    law_foreword: str = Field(alias="LawForeword", default="")
    """法規前言"""

    articles: list[Article] = Field(alias="LawArticles", default_factory=list)
    """條文清單，含章節標題（ArticleType=C）與條文（ArticleType=A）"""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pcode(self) -> str:
        """從 LawURL 解析出的法規唯一識別碼，例如 A0000001"""
        parsed = urlparse(self.law_url)
        params = parse_qs(parsed.query)
        return params.get("pcode", [""])[0]

    @model_validator(mode="after")
    def populate_article_metadata(self) -> "Law":
        """將 pcode 與 law_name 寫入每個 Article，使條文在脫離
        Law 物件後仍能追溯來源法規。

        Returns:
            Law: 已更新 articles 的自身實例（model_validator 慣例）。
        """
        for article in self.articles:
            article.pcode = self.pcode
            article.law_name = self.law_name
        return self
