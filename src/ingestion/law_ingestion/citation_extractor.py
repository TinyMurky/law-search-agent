"""條文引用關係解析器。

解析 Article.artical_content 內的條文引用，
將結果寫入 Article.cited_articles。
cited_articles 格式：(「{pcode}#{ArticleNo}」, CitationType)。

解析優先順序：
1. 範圍引用（至）：第X條至第Y條 → 展開全部
2. 並列引用（及）：第X條及第Y條 → 各引用一次
3. 本法自引：本法第X條 → 使用當前條文的 pcode
   （須在 cross-law 之前，避免「本法」被封鎖器消費）
4. 跨法律引用：民法第X條 → 查 lookup 取得 pcode
   （不在 lookup 的法律也消費位置，避免 bare ref 誤判）
5. 裸露引用：第X條（無法律名稱前綴）→ 視為同法引用
6. 相對引用：前條 / 次條 → 依條文位置推算
"""

import re

from .article import Article
from .chinese_numeral import chinese_to_int
from .citation_types import CitationType
from .law import Law

_CHINESE_NUM = r"[一二三四五六七八九十百千零]+"

_RANGE_ZHI_RE = re.compile(
    rf"第({_CHINESE_NUM})條至第({_CHINESE_NUM})條"
)
_RANGE_JI_RE = re.compile(
    rf"第({_CHINESE_NUM})條及第({_CHINESE_NUM})條"
)
_SELF_REF_RE = re.compile(
    rf"(?:本法|本條例|本辦法|本規則|本細則|本準則|本規程)"
    rf"第({_CHINESE_NUM})條"
)
# 未知法律封鎖器：匹配所有「法律名稱 + 第X條」的位置。
# 僅消費位置，不引用，防止 bare ref 誤判為同法引用。
_UNKNOWN_LAW_BLOCKER_RE = re.compile(
    rf"(?:[^\s，。、；：（）「」\r\n]{{1,20}}?"
    rf"(?:法|條例|辦法|規則|細則|準則|規程))"
    rf"第(?:{_CHINESE_NUM})條"
)
_BARE_RE = re.compile(rf"第({_CHINESE_NUM})條")
_PREV_RE = re.compile(r"前條")
_NEXT_RE = re.compile(r"次條")

_Consumed = set[tuple[int, int]]
_CitedList = list[tuple[str, CitationType]]


class CitationExtractor:
    """從條文內容解析引用關係，寫入 Article.cited_articles。

    lookup table 在 __init__ 注入一次，對所有法律共用。
    """

    def __init__(self, law_name_to_pcode: dict[str, str]) -> None:
        """注入法律名稱與 pcode 的對照表。

        Args:
            law_name_to_pcode (dict[str, str]): 法律名稱對 pcode
                的 lookup table，用於辨識跨法律引用。
        """
        self._lookup = law_name_to_pcode
        self._known_cross_law_re = (
            self._build_known_cross_law_pattern(law_name_to_pcode)
        )

    def extract_from_law(self, law: Law) -> None:
        """解析整部法律的引用，直接寫入各 Article.cited_articles。

        Args:
            law (Law): 要解析引用關係的法律，其 articles 會被
                原地修改。
        """
        ordered = [a for a in law.articles if a.article_type == "A"]
        for article in ordered:
            article.cited_articles = self._extract(article, ordered)

    def _extract(
        self, article: Article, ordered: list[Article]
    ) -> _CitedList:
        """解析單一條文的所有引用，依優先順序套用各規則並去重。

        Args:
            article (Article): 要解析的條文。
            ordered (list[Article]): 同法律中依原順序排列的條文
                清單，供相對引用（前條/次條）定位使用。

        Returns:
            _CitedList: 去重後的引用清單。
        """
        content = article.artical_content
        pcode = article.pcode
        consumed: _Consumed = set()
        cited: _CitedList = []

        cited += self._extract_range_zhi(content, pcode, consumed)
        cited += self._extract_range_ji(content, pcode, consumed)
        cited += self._extract_self_ref(content, pcode, consumed)
        cited += self._extract_cross_law(content, consumed)
        self._consume_unknown_laws(content, consumed)
        cited += self._extract_bare(content, pcode, consumed)
        cited += self._extract_relative(article, ordered, pcode, content)

        # 去重，以 node_id 為 key，保留第一次出現的 CitationType
        seen: dict[str, CitationType] = {}
        for node_id, ctype in cited:
            if node_id not in seen:
                seen[node_id] = ctype
        return list(seen.items())

    def _extract_range_zhi(
        self, content: str, pcode: str, consumed: _Consumed
    ) -> _CitedList:
        """範圍引用（至）→ 展開為連續條文。

        Args:
            content (str): 條文內容。
            pcode (str): 條文所屬法律 pcode。
            consumed (_Consumed): 已消費的文字區間集合，比對後
                會原地更新。

        Returns:
            _CitedList: 展開後的引用清單。
        """
        result: _CitedList = []
        for m in _RANGE_ZHI_RE.finditer(content):
            start = chinese_to_int(m.group(1))
            end = chinese_to_int(m.group(2))
            for n in range(start, end + 1):
                result.append((f"{pcode}#第 {n} 條", "range_zhi"))
            consumed.add((m.start(), m.end()))
        return result

    def _extract_range_ji(
        self, content: str, pcode: str, consumed: _Consumed
    ) -> _CitedList:
        """並列引用（及）→ 各自引用，不展開。

        Args:
            content (str): 條文內容。
            pcode (str): 條文所屬法律 pcode。
            consumed (_Consumed): 已消費的文字區間集合，比對後
                會原地更新。

        Returns:
            _CitedList: 解析後的引用清單。
        """
        result: _CitedList = []
        for m in _RANGE_JI_RE.finditer(content):
            if self._is_consumed(m, consumed):
                continue
            result.append((
                f"{pcode}#第 {chinese_to_int(m.group(1))} 條",
                "range_ji",
            ))
            result.append((
                f"{pcode}#第 {chinese_to_int(m.group(2))} 條",
                "range_ji",
            ))
            consumed.add((m.start(), m.end()))
        return result

    def _extract_self_ref(
        self, content: str, pcode: str, consumed: _Consumed
    ) -> _CitedList:
        """本法自引（本法第X條）。

        Args:
            content (str): 條文內容。
            pcode (str): 條文所屬法律 pcode。
            consumed (_Consumed): 已消費的文字區間集合，比對後
                會原地更新。

        Returns:
            _CitedList: 解析後的引用清單。
        """
        result: _CitedList = []
        for m in _SELF_REF_RE.finditer(content):
            if self._is_consumed(m, consumed):
                continue
            result.append((
                f"{pcode}#第 {chinese_to_int(m.group(1))} 條",
                "self_ref",
            ))
            consumed.add((m.start(), m.end()))
        return result

    def _extract_cross_law(
        self, content: str, consumed: _Consumed
    ) -> _CitedList:
        """已知跨法律引用 — 精準 match lookup 中的法律名稱。

        Args:
            content (str): 條文內容。
            consumed (_Consumed): 已消費的文字區間集合，比對後
                會原地更新。

        Returns:
            _CitedList: 解析後的引用清單。
        """
        result: _CitedList = []
        if not self._known_cross_law_re:
            return result
        for m in self._known_cross_law_re.finditer(content):
            if self._is_consumed(m, consumed):
                continue
            ref_pcode = self._lookup.get(m.group(1), "")
            if ref_pcode:
                no = chinese_to_int(m.group(2))
                result.append(
                    (f"{ref_pcode}#第 {no} 條", "cross_law")
                )
            consumed.add((m.start(), m.end()))
        return result

    def _consume_unknown_laws(
        self, content: str, consumed: _Consumed
    ) -> None:
        """未知法律封鎖 — 消費位置，避免 bare ref 誤判。

        Args:
            content (str): 條文內容。
            consumed (_Consumed): 已消費的文字區間集合，會原地
                更新。
        """
        for m in _UNKNOWN_LAW_BLOCKER_RE.finditer(content):
            if not self._is_consumed(m, consumed):
                consumed.add((m.start(), m.end()))

    def _extract_bare(
        self, content: str, pcode: str, consumed: _Consumed
    ) -> _CitedList:
        """裸露引用（第X條，無法律名稱前綴）→ 同法引用。

        Args:
            content (str): 條文內容。
            pcode (str): 條文所屬法律 pcode。
            consumed (_Consumed): 已消費的文字區間集合。

        Returns:
            _CitedList: 解析後的引用清單。
        """
        result: _CitedList = []
        for m in _BARE_RE.finditer(content):
            if self._is_consumed(m, consumed):
                continue
            result.append((
                f"{pcode}#第 {chinese_to_int(m.group(1))} 條",
                "bare",
            ))
        return result

    def _extract_relative(
        self,
        article: Article,
        ordered: list[Article],
        pcode: str,
        content: str,
    ) -> _CitedList:
        """相對引用（前條 / 次條）→ 依條文位置推算。

        Args:
            article (Article): 要解析的條文。
            ordered (list[Article]): 同法律中依原順序排列的條文
                清單。
            pcode (str): 條文所屬法律 pcode。
            content (str): 條文內容。

        Returns:
            _CitedList: 解析後的引用清單，找不到 article 在
                ordered 中的位置時回傳空清單。
        """
        result: _CitedList = []
        try:
            idx = next(
                i
                for i, a in enumerate(ordered)
                if a.article_no == article.article_no
            )
        except StopIteration:
            return result

        if _PREV_RE.search(content) and idx > 0:
            result.append((
                f"{pcode}#{ordered[idx - 1].article_no}",
                "relative",
            ))
        if _NEXT_RE.search(content) and idx < len(ordered) - 1:
            result.append((
                f"{pcode}#{ordered[idx + 1].article_no}",
                "relative",
            ))

        return result

    @staticmethod
    def _build_known_cross_law_pattern(
        lookup: dict[str, str],
    ) -> re.Pattern | None:
        """依 lookup table 建立已知跨法律引用的合併 regex。

        長名稱優先排序，避免短名稱（如「任用法」）提前 match
        應屬於長名稱（如「公務人員任用法」）的引用。

        Args:
            lookup (dict[str, str]): 法律名稱對 pcode 的
                lookup table。

        Returns:
            re.Pattern | None: 合併後的 regex，lookup 為空時
                回傳 None。
        """
        if not lookup:
            return None
        # 長名稱優先，避免短名稱提前 match
        # 例如「任用法」不應比「公務人員任用法」先 match
        sorted_names = sorted(lookup.keys(), key=len, reverse=True)
        names_alt = "|".join(re.escape(n) for n in sorted_names)
        return re.compile(rf"({names_alt})第({_CHINESE_NUM})條")

    @staticmethod
    def _is_consumed(
        m: re.Match, consumed: _Consumed
    ) -> bool:
        """判斷 regex match 的起始位置是否已被其他規則消費。

        Args:
            m (re.Match): 目前的 regex match。
            consumed (_Consumed): 已消費的文字區間集合。

        Returns:
            bool: 起始位置落在任一已消費區間內則為 True。
        """
        return any(s <= m.start() < e for s, e in consumed)
