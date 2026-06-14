from __future__ import annotations

from dataclasses import dataclass

from langchain_core.documents import Document

from ingestion.law_ingestion.article import Article


@dataclass
class ArticleChunk:
    """Article 在 Chroma chunks collection 中的表示。

    負責 ingestion Article 與 Chroma Document 之間的雙向轉換。
    cited_articles 不存入 Chroma，因此此類別不含該欄位。
    score 僅於 similarity_search 時有值，peek 時為 None。

    Attributes:
        pcode (str): 所屬法規唯一識別碼，例如 A0000001。
        law_name (str): 所屬法規名稱，例如「民法」。
        article_no (str): 條號，例如「第 184 條」。
        artical_content (str): 條文內容。
        law_modified_date (str): 法規最後修改日期，例如 20240101。
        score (float | None): 語意搜尋相似度分數，peek 時為 None。
    """

    pcode: str
    law_name: str
    article_no: str
    artical_content: str
    law_modified_date: str
    score: float | None = None

    @classmethod
    def from_article(
        cls,
        article: Article,
        law_modified_date: str,
    ) -> ArticleChunk:
        """ingestion Article 轉換為 ArticleChunk。

        Args:
            article (Article): ingestion 層的條文物件。
            law_modified_date (str): 父 Law 的修改日期，
                Article 本身不含此欄位。

        Returns:
            ArticleChunk: 對應的 ArticleChunk 實例。
        """
        return cls(
            pcode=article.pcode,
            law_name=article.law_name,
            article_no=article.article_no,
            artical_content=article.artical_content,
            law_modified_date=law_modified_date,
        )

    @classmethod
    def from_chroma(
        cls,
        doc: Document,
        score: float | None = None,
    ) -> ArticleChunk:
        """Chroma 取出的 Document 轉換為 ArticleChunk。

        page_content 格式為 to_document() 產生的
        "{law_name} {article_no}\\n{artical_content}"，
        以第一個換行切出 artical_content。

        Args:
            doc (Document): Chroma 回傳的 LangChain Document。
            score (float | None): 語意搜尋相似度分數，
                peek 時不傳入，預設為 None。

        Returns:
            ArticleChunk: 對應的 ArticleChunk 實例。
        """
        meta = doc.metadata
        _, content = doc.page_content.split("\n", 1)
        return cls(
            pcode=str(meta["pcode"]),
            law_name=str(meta["law_name"]),
            article_no=str(meta["article_no"]),
            artical_content=content,
            law_modified_date=str(meta["law_modified_date"]),
            score=score,
        )

    def to_node_id(self) -> str:
        """Chroma ID 與 NetworkX node ID 共用的識別字串。

        Returns:
            str: "{pcode}#{article_no}" 格式，例如 "B0000001#第 184 條"。
        """
        return f"{self.pcode}#{self.article_no}"

    def to_document(self) -> str:
        """存入 Chroma 的 embed 文字。

        含法律名稱與條號前綴，讓 embedding 帶有來源語境，
        提升語意搜尋準確度。

        Returns:
            str: "{law_name} {article_no}\\n{artical_content}" 格式。
        """
        return (
            f"{self.law_name} {self.article_no}\n"
            f"{self.artical_content}"
        )

    def to_metadata(self) -> dict[str, str]:
        """存入 Chroma 的 metadata。

        供 filtering 條件與 from_chroma() 還原使用。

        Returns:
            dict[str, str]: pcode、article_no、law_name、
                law_modified_date 四個欄位。
        """
        return {
            "pcode": self.pcode,
            "article_no": self.article_no,
            "law_name": self.law_name,
            "law_modified_date": self.law_modified_date,
        }

    def to_prompt(self) -> str:
        """給 LLM 的條文字串。

        Returns:
            str: "{law_name} {article_no}\\n{artical_content}" 格式。
        """
        return (
            f"{self.law_name} {self.article_no}\n"
            f"{self.artical_content}"
        )
