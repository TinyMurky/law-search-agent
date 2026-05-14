"""中文數字轉換器，專為台灣法條條號設計，支援 1–9999。

台灣法律慣用格式特殊處理：
- 「一百十」= 110（百位後省略零，直接接十位）
- 「一千零三」= 1003（千位後以零銜接個位）
"""

_DIGIT: dict[str, int] = {
    "一": 1,
    "二": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}


def chinese_to_int(s: str) -> int:
    """將中文數字字串轉換為整數。

    Args:
        s: 中文數字字串，例如「二十二」、「一百零三」、「一千一百七十三」

    Returns:
        對應的整數

    Raises:
        ValueError: 輸入為空或包含無法辨識的字元
    """
    s = s.strip()
    if not s:
        raise ValueError("輸入不可為空字串")

    result = 0

    # 千位
    if "千" in s:
        idx = s.index("千")
        thousands_char = s[:idx]
        if thousands_char not in _DIGIT:
            raise ValueError(f"無法解析千位：{s!r}")
        result += _DIGIT[thousands_char] * 1000
        s = s[idx + 1:]

    # 移除千位與百位之間的零（如「一千零三百」，實際罕見）
    s = s.lstrip("零")

    # 百位
    if "百" in s:
        idx = s.index("百")
        hundreds_char = s[:idx]
        if hundreds_char not in _DIGIT:
            raise ValueError(f"無法解析百位：{s!r}")
        result += _DIGIT[hundreds_char] * 100
        s = s[idx + 1:]

    # 移除百位與十位之間的零（如「一百零三」→ 「三」）
    s = s.lstrip("零")

    result += _parse_under_hundred(s)
    return result


def _parse_under_hundred(s: str) -> int:
    """解析 0–99 的中文數字。"""
    if not s:
        return 0

    if "十" not in s:
        if s not in _DIGIT:
            raise ValueError(f"無法解析：{s!r}")
        return _DIGIT[s]

    idx = s.index("十")
    tens_char = s[:idx]
    ones_char = s[idx + 1:]

    # 十 開頭（tens_char 為空）視為 1×10，例如「十」= 10、「十一」= 11
    if tens_char == "":
        tens = 10
    elif tens_char in _DIGIT:
        tens = _DIGIT[tens_char] * 10
    else:
        raise ValueError(f"無法解析十位：{s!r}")

    if ones_char == "":
        ones = 0
    elif ones_char in _DIGIT:
        ones = _DIGIT[ones_char]
    else:
        raise ValueError(f"無法解析個位：{s!r}")

    return tens + ones
