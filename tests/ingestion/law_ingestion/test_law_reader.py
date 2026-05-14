import json
from pathlib import Path

import pytest

from ingestion.law_ingestion.law_reader import LawReader


@pytest.fixture
def sample_json(tmp_path: Path) -> Path:
    data = {
        "UpdateDate": "2026/4/30 上午 12:00:00",
        "Laws": [
            {
                "LawLevel": "憲法",
                "LawName": "中華民國憲法",
                "LawURL": (
                    "https://law.moj.gov.tw/LawClass/"
                    "LawAll.aspx?pcode=A0000001"
                ),
                "LawCategory": "憲法",
                "LawModifiedDate": "19470101",
                "LawAttachements": [],
                "LawArticles": [
                    {
                        "ArticleType": "A",
                        "ArticleNo": "第 1 條",
                        "ArticleContent": "中華民國基於三民主義。",
                    }
                ],
            },
            {
                "LawLevel": "法律",
                "LawName": "民法",
                "LawURL": (
                    "https://law.moj.gov.tw/LawClass/"
                    "LawAll.aspx?pcode=B0000001"
                ),
                "LawCategory": "民事",
                "LawModifiedDate": "20240101",
                "LawAttachements": [],
                "LawArticles": [],
            },
        ],
    }
    p = tmp_path / "ChLaw.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


@pytest.fixture
def bom_json(tmp_path: Path) -> Path:
    """UTF-8 BOM 編碼檔案，模擬真實資料來源"""
    data = {
        "UpdateDate": "2026/4/30",
        "Laws": [
            {
                "LawLevel": "法律",
                "LawName": "測試法",
                "LawURL": (
                    "https://law.moj.gov.tw/LawClass/"
                    "LawAll.aspx?pcode=C0000001"
                ),
                "LawCategory": "行政",
                "LawModifiedDate": "20240101",
                "LawAttachements": [],
                "LawArticles": [],
            }
        ],
    }
    p = tmp_path / "ChLaw_bom.json"
    p.write_text(json.dumps(data), encoding="utf-8-sig")
    return p


def test_load_returns_correct_count(sample_json: Path) -> None:
    laws = LawReader(sample_json).load()
    assert len(laws) == 2


def test_load_law_names(sample_json: Path) -> None:
    laws = LawReader(sample_json).load()
    names = [law.law_name for law in laws]
    assert "中華民國憲法" in names
    assert "民法" in names


def test_load_pcode_extracted(sample_json: Path) -> None:
    laws = LawReader(sample_json).load()
    pcodes = {law.pcode for law in laws}
    assert "A0000001" in pcodes
    assert "B0000001" in pcodes


def test_load_articles_populated(sample_json: Path) -> None:
    laws = LawReader(sample_json).load()
    constitution = next(l for l in laws if l.pcode == "A0000001")
    assert len(constitution.articles) == 1
    assert constitution.articles[0].pcode == "A0000001"
    assert constitution.articles[0].law_name == "中華民國憲法"


def test_load_bom_encoding(bom_json: Path) -> None:
    laws = LawReader(bom_json).load()
    assert len(laws) == 1
    assert laws[0].law_name == "測試法"


def test_load_accepts_string_path(sample_json: Path) -> None:
    laws = LawReader(str(sample_json)).load()
    assert len(laws) == 2


def test_build_name_to_pcode(sample_json: Path) -> None:
    reader = LawReader(sample_json)
    laws = reader.load()
    lookup = reader.build_name_to_pcode(laws)
    assert lookup["中華民國憲法"] == "A0000001"
    assert lookup["民法"] == "B0000001"


def test_build_name_to_pcode_empty() -> None:
    reader = LawReader.__new__(LawReader)
    assert reader.build_name_to_pcode([]) == {}
