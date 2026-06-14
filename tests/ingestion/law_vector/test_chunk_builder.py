from pathlib import Path

import pytest
from langchain_core.embeddings import Embeddings

from ingestion.law_ingestion.law import Law
from ingestion.law_vector.article_chunk import ArticleChunk
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


def test_build_returns_newly_added_count(
    builder: ChunkBuilder, law: Law
) -> None:
    count = builder.build([law])
    assert count == 2  # 2 "A" articles; 1 "C" chapter is skipped


def test_build_is_idempotent(
    builder: ChunkBuilder, law: Law
) -> None:
    builder.build([law])
    second = builder.build([law])
    assert second == 0        # nothing new to add
    assert builder.count() == 2  # DB unchanged


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


# ── peek_chunks ───────────────────────────────────────────────────────


def test_peek_chunks_returns_article_chunk(
    builder: ChunkBuilder, law: Law
) -> None:
    builder.build([law])
    results = builder.peek_chunks(2)
    assert all(isinstance(r, ArticleChunk) for r in results)


def test_peek_chunks_respects_limit(
    builder: ChunkBuilder, law: Law
) -> None:
    builder.build([law])
    results = builder.peek_chunks(1)
    assert len(results) == 1


def test_peek_chunks_node_id_format(
    builder: ChunkBuilder, law: Law
) -> None:
    builder.build([law])
    results = builder.peek_chunks(2)
    for chunk in results:
        assert "#" in chunk.to_node_id()


def test_peek_chunks_score_is_none(
    builder: ChunkBuilder, law: Law
) -> None:
    builder.build([law])
    results = builder.peek_chunks(2)
    for chunk in results:
        assert chunk.score is None


def test_peek_chunks_law_name(
    builder: ChunkBuilder, law: Law
) -> None:
    builder.build([law])
    results = builder.peek_chunks(2)
    for chunk in results:
        assert chunk.law_name == "民法"


# ── search_chunks ─────────────────────────────────────────────────────


def test_search_chunks_returns_article_chunk(
    builder: ChunkBuilder, law: Law
) -> None:
    builder.build([law])
    results = builder.search_chunks("民法", k=2)
    assert all(isinstance(r, ArticleChunk) for r in results)


def test_search_chunks_count(
    builder: ChunkBuilder, law: Law
) -> None:
    builder.build([law])
    results = builder.search_chunks("民法", k=2)
    assert len(results) == 2


def test_search_chunks_node_id_format(
    builder: ChunkBuilder, law: Law
) -> None:
    builder.build([law])
    results = builder.search_chunks("民法", k=2)
    for chunk in results:
        assert "#" in chunk.to_node_id()


def test_search_chunks_law_name(
    builder: ChunkBuilder, law: Law
) -> None:
    builder.build([law])
    results = builder.search_chunks("民法", k=2)
    for chunk in results:
        assert chunk.law_name == "民法"


def test_search_chunks_has_score(
    builder: ChunkBuilder, law: Law
) -> None:
    builder.build([law])
    results = builder.search_chunks("民法", k=2)
    for chunk in results:
        assert chunk.score is not None
