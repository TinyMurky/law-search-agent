import pytest
from langchain_core.documents import Document

from ingestion.law_ingestion.article import Article
from ingestion.law_vector.article_chunk import ArticleChunk

_PCODE = "B0000001"
_LAW_NAME = "民法"
_ARTICLE_NO = "第 184 條"
_CONTENT = "因故意或過失，不法侵害他人之權利者，負損害賠償責任。"
_MODIFIED_DATE = "20240101"
_EXPECTED_DOCUMENT = f"{_LAW_NAME} {_ARTICLE_NO}\n{_CONTENT}"
_EXPECTED_NODE_ID = f"{_PCODE}#{_ARTICLE_NO}"


@pytest.fixture
def article() -> Article:
    return Article(
        article_type="A",
        article_no=_ARTICLE_NO,
        artical_content=_CONTENT,
        pcode=_PCODE,
        law_name=_LAW_NAME,
    )


@pytest.fixture
def chunk() -> ArticleChunk:
    return ArticleChunk(
        pcode=_PCODE,
        law_name=_LAW_NAME,
        article_no=_ARTICLE_NO,
        artical_content=_CONTENT,
        law_modified_date=_MODIFIED_DATE,
    )


@pytest.fixture
def chroma_doc() -> Document:
    return Document(
        page_content=_EXPECTED_DOCUMENT,
        metadata={
            "pcode": _PCODE,
            "law_name": _LAW_NAME,
            "article_no": _ARTICLE_NO,
            "law_modified_date": _MODIFIED_DATE,
        },
    )


# ── from_article ──────────────────────────────────────────────────────


def test_from_article_pcode(article: Article) -> None:
    chunk = ArticleChunk.from_article(article, _MODIFIED_DATE)
    assert chunk.pcode == _PCODE


def test_from_article_law_name(article: Article) -> None:
    chunk = ArticleChunk.from_article(article, _MODIFIED_DATE)
    assert chunk.law_name == _LAW_NAME


def test_from_article_article_no(article: Article) -> None:
    chunk = ArticleChunk.from_article(article, _MODIFIED_DATE)
    assert chunk.article_no == _ARTICLE_NO


def test_from_article_content(article: Article) -> None:
    chunk = ArticleChunk.from_article(article, _MODIFIED_DATE)
    assert chunk.artical_content == _CONTENT


def test_from_article_law_modified_date(article: Article) -> None:
    chunk = ArticleChunk.from_article(article, _MODIFIED_DATE)
    assert chunk.law_modified_date == _MODIFIED_DATE


def test_from_article_score_defaults_none(article: Article) -> None:
    chunk = ArticleChunk.from_article(article, _MODIFIED_DATE)
    assert chunk.score is None


# ── from_chroma ───────────────────────────────────────────────────────


def test_from_chroma_pcode(chroma_doc: Document) -> None:
    chunk = ArticleChunk.from_chroma(chroma_doc)
    assert chunk.pcode == _PCODE


def test_from_chroma_law_name(chroma_doc: Document) -> None:
    chunk = ArticleChunk.from_chroma(chroma_doc)
    assert chunk.law_name == _LAW_NAME


def test_from_chroma_article_no(chroma_doc: Document) -> None:
    chunk = ArticleChunk.from_chroma(chroma_doc)
    assert chunk.article_no == _ARTICLE_NO


def test_from_chroma_content_strips_prefix(chroma_doc: Document) -> None:
    chunk = ArticleChunk.from_chroma(chroma_doc)
    assert chunk.artical_content == _CONTENT


def test_from_chroma_law_modified_date(chroma_doc: Document) -> None:
    chunk = ArticleChunk.from_chroma(chroma_doc)
    assert chunk.law_modified_date == _MODIFIED_DATE


def test_from_chroma_score_defaults_none(chroma_doc: Document) -> None:
    chunk = ArticleChunk.from_chroma(chroma_doc)
    assert chunk.score is None


def test_from_chroma_score_set(chroma_doc: Document) -> None:
    chunk = ArticleChunk.from_chroma(chroma_doc, score=0.85)
    assert chunk.score == pytest.approx(0.85)


# ── to_node_id ────────────────────────────────────────────────────────


def test_to_node_id_format(chunk: ArticleChunk) -> None:
    assert chunk.to_node_id() == _EXPECTED_NODE_ID


# ── to_document ───────────────────────────────────────────────────────


def test_to_document_format(chunk: ArticleChunk) -> None:
    assert chunk.to_document() == _EXPECTED_DOCUMENT


def test_to_document_contains_law_name(chunk: ArticleChunk) -> None:
    assert _LAW_NAME in chunk.to_document()


def test_to_document_contains_article_no(chunk: ArticleChunk) -> None:
    assert _ARTICLE_NO in chunk.to_document()


def test_to_document_contains_content(chunk: ArticleChunk) -> None:
    assert _CONTENT in chunk.to_document()


# ── to_metadata ───────────────────────────────────────────────────────


def test_to_metadata_keys(chunk: ArticleChunk) -> None:
    keys = set(chunk.to_metadata().keys())
    assert keys == {"pcode", "article_no", "law_name", "law_modified_date"}


def test_to_metadata_values(chunk: ArticleChunk) -> None:
    meta = chunk.to_metadata()
    assert meta["pcode"] == _PCODE
    assert meta["article_no"] == _ARTICLE_NO
    assert meta["law_name"] == _LAW_NAME
    assert meta["law_modified_date"] == _MODIFIED_DATE


# ── to_prompt ─────────────────────────────────────────────────────────


def test_to_prompt_format(chunk: ArticleChunk) -> None:
    assert chunk.to_prompt() == _EXPECTED_DOCUMENT


# ── round-trip ────────────────────────────────────────────────────────


def test_round_trip_from_article_to_document(article: Article) -> None:
    chunk = ArticleChunk.from_article(article, _MODIFIED_DATE)
    assert chunk.to_document() == _EXPECTED_DOCUMENT


def test_round_trip_from_chroma_preserves_content(
    chunk: ArticleChunk,
) -> None:
    doc = Document(
        page_content=chunk.to_document(),
        metadata=chunk.to_metadata(),
    )
    restored = ArticleChunk.from_chroma(doc, score=0.9)
    assert restored.pcode == chunk.pcode
    assert restored.law_name == chunk.law_name
    assert restored.article_no == chunk.article_no
    assert restored.artical_content == chunk.artical_content
    assert restored.law_modified_date == chunk.law_modified_date
