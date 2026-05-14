import pytest

from ingestion.law_ingestion.chinese_numeral import chinese_to_int


@pytest.mark.parametrize("chinese, expected", [
    # 個位
    ("一", 1),
    ("九", 9),
    # 十位
    ("十", 10),
    ("十一", 11),
    ("十九", 19),
    ("二十", 20),
    ("二十一", 21),
    ("九十九", 99),
    # 百位（一般）
    ("一百", 100),
    ("一百零一", 101),
    ("一百零九", 109),
    ("一百二十三", 123),
    ("九百九十九", 999),
    # 百位（台灣法律慣用：百位後省略零直接接十位）
    ("一百十", 110),
    ("一百十二", 112),
    ("一百十五", 115),
    # 百位（含明確一十）
    ("一百一十", 110),
    ("一百一十一", 111),
    # 千位（民法實際出現的條號）
    ("一千", 1000),
    ("一千零三", 1003),
    ("一千一百", 1100),
    ("一千一百七十三", 1173),
    ("一千一百七十九", 1179),
    ("一千一百九十八", 1198),
    ("一千二百二十五", 1225),
])
def test_chinese_to_int(chinese: str, expected: int) -> None:
    assert chinese_to_int(chinese) == expected


def test_strips_whitespace() -> None:
    assert chinese_to_int("  二十二  ") == 22


def test_empty_string_raises() -> None:
    with pytest.raises(ValueError):
        chinese_to_int("")


def test_invalid_character_raises() -> None:
    with pytest.raises(ValueError):
        chinese_to_int("abc")
