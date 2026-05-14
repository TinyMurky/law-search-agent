import pytest

from ingestion.law_ingestion.article import Article
from ingestion.law_ingestion.citation_extractor import CitationExtractor

PCODE = "A0000001"
CIVIL_PCODE = "B0000001"

LOOKUP = {"民法": CIVIL_PCODE, "刑法": "C0000001"}


def make_article(content: str, article_no: str = "第 1 條") -> Article:
    return Article(
        article_type="A",
        article_no=article_no,
        artical_content=content,
        pcode=PCODE,
        law_name="測試法",
    )


@pytest.fixture
def extractor() -> CitationExtractor:
    return CitationExtractor(LOOKUP)


# --- 範圍引用（至）---

def test_range_zhi_expands(extractor):
    article = make_article("依第二十五條至第二十七條規定")
    result = extractor._extract(article, [article])
    assert result == [
        f"{PCODE}#第 25 條",
        f"{PCODE}#第 26 條",
        f"{PCODE}#第 27 條",
    ]


# --- 並列引用（及）---

def test_range_ji_cites_both_only(extractor):
    article = make_article("依第九十七條及第九十八條規定")
    result = extractor._extract(article, [article])
    assert f"{PCODE}#第 97 條" in result
    assert f"{PCODE}#第 98 條" in result
    # 不應展開中間的條文
    assert f"{PCODE}#第 97 條" in result
    assert len([r for r in result if "條" in r]) == 2


def test_range_ji_non_consecutive(extractor):
    article = make_article("依第四條及第十三條規定")
    result = extractor._extract(article, [article])
    assert f"{PCODE}#第 4 條" in result
    assert f"{PCODE}#第 13 條" in result
    # 中間的條文不應出現
    assert f"{PCODE}#第 5 條" not in result


# --- 跨法律引用 ---

def test_cross_law_citation(extractor):
    article = make_article("依民法第七十條規定")
    result = extractor._extract(article, [article])
    assert f"{CIVIL_PCODE}#第 70 條" in result


def test_cross_law_not_in_lookup(extractor):
    article = make_article("依海商法第五條規定")
    result = extractor._extract(article, [article])
    assert result == []


# --- 本法自引 ---

def test_self_ref(extractor):
    article = make_article("依本法第二十七條規定")
    result = extractor._extract(article, [article])
    assert f"{PCODE}#第 27 條" in result


def test_self_ref_bendiaoli(extractor):
    article = make_article(
        pcode_article := "依本條例第四條規定",
    )
    a = Article(
        article_type="A",
        article_no="第 1 條",
        artical_content="依本條例第四條規定",
        pcode=PCODE,
        law_name="測試條例",
    )
    result = extractor._extract(a, [a])
    assert f"{PCODE}#第 4 條" in result


# --- 裸露引用 ---

def test_bare_ref(extractor):
    article = make_article("依第七條規定辦理")
    result = extractor._extract(article, [article])
    assert f"{PCODE}#第 7 條" in result


def test_bare_ref_not_duplicated_when_also_cross_law(extractor):
    # 「民法第七十條」應只計一次（cross-law），不應再被 bare 重複計入
    article = make_article("依民法第七十條規定")
    result = extractor._extract(article, [article])
    assert result.count(f"{CIVIL_PCODE}#第 70 條") == 1


# --- 相對引用 ---

def _make_ordered(contents: list[str]) -> list[Article]:
    return [
        Article(
            article_type="A",
            article_no=f"第 {i + 1} 條",
            artical_content=content,
            pcode=PCODE,
            law_name="測試法",
        )
        for i, content in enumerate(contents)
    ]


def test_prev_article(extractor):
    ordered = _make_ordered(["第一條內容", "依前條規定"])
    result = extractor._extract(ordered[1], ordered)
    assert f"{PCODE}#第 1 條" in result


def test_next_article(extractor):
    ordered = _make_ordered(["依次條規定", "第二條內容"])
    result = extractor._extract(ordered[0], ordered)
    assert f"{PCODE}#第 2 條" in result


def test_prev_at_first_article_ignored(extractor):
    ordered = _make_ordered(["依前條規定"])
    result = extractor._extract(ordered[0], ordered)
    assert result == []


# --- 去重 ---

def test_deduplication(extractor):
    article = make_article("依本法第七條及本法第七條規定")
    result = extractor._extract(article, [article])
    assert result.count(f"{PCODE}#第 7 條") == 1
