import pytest

from ingestion.law_ingestion.law import Law


@pytest.fixture
def raw_law() -> dict:
    return {
        "LawLevel": "憲法",
        "LawName": "中華民國憲法",
        "LawURL": "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0000001",
        "LawCategory": "憲法",
        "LawModifiedDate": "19470101",
        "LawEffectiveDate": "",
        "LawEffectiveNote": "",
        "LawAbandonNote": "",
        "LawHasEngVersion": "Y",
        "EngLawName": "Constitution of the Republic of China (Taiwan)",
        "LawAttachements": [],
        "LawHistories": "",
        "LawForeword": "",
        "LawArticles": [
            {
                "ArticleType": "C",
                "ArticleNo": "",
                "ArticleContent": "第 一 章 總綱",
            },
            {
                "ArticleType": "A",
                "ArticleNo": "第 1 條",
                "ArticleContent": "中華民國基於三民主義，為民有民治民享之民主共和國。",
            },
        ],
    }


def test_pcode_extracted_from_url(raw_law):
    law = Law.model_validate(raw_law)
    assert law.pcode == "A0000001"


def test_articles_populated_with_pcode(raw_law):
    law = Law.model_validate(raw_law)
    for article in law.articles:
        assert article.pcode == "A0000001"


def test_articles_populated_with_law_name(raw_law):
    law = Law.model_validate(raw_law)
    for article in law.articles:
        assert article.law_name == "中華民國憲法"


def test_optional_fields_default_empty():
    law = Law.model_validate(
        {
            "LawLevel": "法律",
            "LawName": "測試法",
            "LawURL": "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=B0000001",
            "LawCategory": "行政",
            "LawModifiedDate": "20240101",
        }
    )
    assert law.law_effective_date == ""
    assert law.law_effective_note == ""
    assert law.law_abandon_note == ""
    assert law.law_attachments == []
    assert law.articles == []


def test_attachment_parsed():
    law = Law.model_validate(
        {
            "LawLevel": "法律",
            "LawName": "立法院組織法",
            "LawURL": "https://law.moj.gov.tw/LawClass/LawAll.aspx?pcode=A0010001",
            "LawCategory": "憲政",
            "LawModifiedDate": "20240101",
            "LawAttachements": [
                {
                    "FileName": "附表.PDF",
                    "FileURL": "https://law.moj.gov.tw/LawClass/LawGetFile.ashx?FileId=0000357850",
                }
            ],
        }
    )
    assert len(law.law_attachments) == 1
    assert law.law_attachments[0].file_name == "附表.PDF"
    assert "FileId=0000357850" in law.law_attachments[0].file_url
