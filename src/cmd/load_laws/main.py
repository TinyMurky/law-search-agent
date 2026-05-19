from pathlib import Path

from ingestion.law_graph.builder import LawGraphBuilder
from ingestion.law_graph.nx_law_graph import NxLawGraph
from ingestion.law_ingestion.citation_extractor import (
    CitationExtractor,
)
from ingestion.law_ingestion.law import Law
from ingestion.law_ingestion.law_reader import LawReader

_DATA_PATH = Path("raw_data/laws/ChLaw.json")


def _print_stats(laws: list[Law]) -> None:
    total_articles = sum(
        1
        for law in laws
        for a in law.articles
        if a.article_type == "A"
    )
    total_citations = sum(
        len(a.cited_articles)
        for law in laws
        for a in law.articles
        if a.article_type == "A"
    )
    print(f"法律數量：{len(laws)} 部")
    print(f"條文數量：{total_articles} 條")
    print(f"引用關係：{total_citations} 筆")


def _find_sample(
    laws: list[Law],
) -> tuple[str, str, str] | None:
    """找第一個有引用關係的條文，回傳 (law_name, pcode, article_no)。"""
    for law in laws:
        for article in law.articles:
            has_cite = (
                article.article_type == "A"
                and article.cited_articles
            )
            if has_cite:
                return law.law_name, article.pcode, article.article_no
    return None


def _print_graph_demo(
    laws: list[Law], graph: NxLawGraph
) -> None:
    sample = _find_sample(laws)
    if not sample:
        print("找不到有引用關係的條文")
        return

    law_name, pcode, article_no = sample
    articles = graph.get_law_articles(pcode)
    cited = graph.get_cited_articles(pcode, article_no)
    citing = graph.get_citing_articles(pcode, article_no)

    print(f"\n--- 圖查詢示範：{law_name} ---")
    print(f"該法共 {len(articles)} 條條文")
    print(f"\n{article_no} 引用 {len(cited)} 條：")
    for c in cited[:5]:
        print(f"  → {c}")
    print(f"\n{article_no} 被引用 {len(citing)} 次")


def main() -> None:
    print("載入法律資料...")
    reader = LawReader(_DATA_PATH)
    laws = reader.load()

    print("解析條文引用...")
    lookup = reader.build_name_to_pcode(laws)
    extractor = CitationExtractor(lookup)
    for law in laws:
        extractor.extract_from_law(law)

    _print_stats(laws)

    print("\n建立圖結構...")
    graph = LawGraphBuilder().build(laws)
    _print_graph_demo(laws, graph)


if __name__ == "__main__":
    main()
