from pathlib import Path

import pytest
from langchain_core.embeddings import Embeddings

from ingestion.law_ingestion.law import Law
from ingestion.law_vector.chunk_builder import ChunkBuilder

_LAW_URL = (
    "https://law.moj.gov.tw/LawClass/LawAll.aspx"
    "?pcode=B0000001"
)


class _FakeEmbeddings(Embeddings):
    """Zero-API embeddings for testing (fixed 10-dim vectors)."""

    def embed_documents(
        self, texts: list[str]
    ) -> list[list[float]]:
        return [[0.1] * 10 for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [0.1] * 10


def _make_law() -> Law:
    return Law.model_validate({
        "LawLevel": "法律",
        "LawName": "民法",
        "LawURL": _LAW_URL,
        "LawCategory": "民事",
        "LawModifiedDate": "20240101",
        "LawEffectiveDate": "",
        "LawEffectiveNote": "",
        "LawAbandonNote": "",
        "LawHasEngVersion": "",
        "EngLawName": "",
        "LawAttachements": [],
        "LawHistories": "",
        "LawForeword": "",
        "LawArticles": [
            {
                "ArticleType": "A",
                "ArticleNo": "第 1 條",
                "ArticleContent": "民法第一條測試內容",
            },
            {
                "ArticleType": "A",
                "ArticleNo": "第 2 條",
                "ArticleContent": "民法第二條測試內容",
            },
            {
                "ArticleType": "C",
                "ArticleNo": "",
                "ArticleContent": "第一章 通則",
            },
        ],
    })


@pytest.fixture
def fake_embeddings() -> _FakeEmbeddings:
    return _FakeEmbeddings()


@pytest.fixture
def law() -> Law:
    return _make_law()


@pytest.fixture
def builder(
    tmp_path: Path, fake_embeddings: _FakeEmbeddings
) -> ChunkBuilder:
    return ChunkBuilder(
        persist_directory=str(tmp_path / "chroma"),
        embeddings=fake_embeddings,
    )


def test_count_empty(builder: ChunkBuilder) -> None:
    assert builder.count() == 0


def test_is_populated_false_initially(
    builder: ChunkBuilder,
) -> None:
    assert not builder.is_populated()


def test_build_returns_article_count(
    builder: ChunkBuilder, law: Law
) -> None:
    count = builder.build([law])
    assert count == 2  # 2 "A" articles; 1 "C" chapter is skipped


def test_count_after_build(
    builder: ChunkBuilder, law: Law
) -> None:
    builder.build([law])
    assert builder.count() == 2


def test_is_populated_after_build(
    builder: ChunkBuilder, law: Law
) -> None:
    builder.build([law])
    assert builder.is_populated()


def test_clear_resets_count(
    builder: ChunkBuilder, law: Law
) -> None:
    builder.build([law])
    builder.clear()
    assert builder.count() == 0


def test_peek_structure(
    builder: ChunkBuilder, law: Law
) -> None:
    builder.build([law])
    results = builder.peek(2)
    assert len(results) == 2
    for r in results:
        assert "id" in r
        assert "document" in r
        assert "metadata" in r


def test_peek_id_contains_separator(
    builder: ChunkBuilder, law: Law
) -> None:
    builder.build([law])
    results = builder.peek(2)
    for r in results:
        assert "#" in str(r["id"])


def test_peek_respects_limit(
    builder: ChunkBuilder, law: Law
) -> None:
    builder.build([law])
    results = builder.peek(1)
    assert len(results) == 1


def test_search_structure(
    builder: ChunkBuilder, law: Law
) -> None:
    builder.build([law])
    results = builder.search("民法", k=2)
    assert len(results) == 2
    for r in results:
        assert "node_id" in r
        assert "law_name" in r
        assert "article_no" in r
        assert "content" in r
        assert "score" in r


def test_search_node_id_format(
    builder: ChunkBuilder, law: Law
) -> None:
    builder.build([law])
    results = builder.search("民法", k=2)
    for r in results:
        assert "#" in str(r["node_id"])


def test_search_law_name_matches(
    builder: ChunkBuilder, law: Law
) -> None:
    builder.build([law])
    results = builder.search("民法", k=2)
    for r in results:
        assert r["law_name"] == "民法"
