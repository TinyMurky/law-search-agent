import pytest

from ingestion.law_ingestion.article import Article


@pytest.fixture
def raw_article() -> dict:
    return {
        "ArticleType": "A",
        "ArticleNo": "第 1 條",
        "ArticleContent": "中華民國基於三民主義，為民有民治民享之民主共和國。",
    }


@pytest.fixture
def raw_chapter() -> dict:
    return {
        "ArticleType": "C",
        "ArticleNo": "",
        "ArticleContent": "第 一 章 總綱",
    }


def test_article_parsed_from_alias(raw_article):
    article = Article.model_validate(raw_article)
    assert article.article_type == "A"
    assert article.article_no == "第 1 條"
    assert article.artical_content == "中華民國基於三民主義，為民有民治民享之民主共和國。"


def test_article_chapter_header_parsed(raw_chapter):
    chapter = Article.model_validate(raw_chapter)
    assert chapter.article_type == "C"
    assert chapter.article_no == ""


def test_article_pcode_defaults_empty(raw_article):
    article = Article.model_validate(raw_article)
    assert article.pcode == ""


def test_article_law_name_defaults_empty(raw_article):
    article = Article.model_validate(raw_article)
    assert article.law_name == ""


def test_article_cited_articles_defaults_empty(raw_article):
    article = Article.model_validate(raw_article)
    assert article.cited_articles == []


def test_article_created_by_field_name():
    article = Article(
        article_type="A",
        article_no="第 1 條",
        artical_content="測試條文內容",
        pcode="A0000001",
        law_name="中華民國憲法",
    )
    assert article.pcode == "A0000001"
    assert article.law_name == "中華民國憲法"
