import logging
from pathlib import Path

from ingestion.law_graph.builder import LawGraphBuilder
from ingestion.law_graph.nx_law_graph import NxLawGraph
from ingestion.law_ingestion.citation_extractor import (
    CitationExtractor,
)
from ingestion.law_ingestion.law import Law
from ingestion.law_ingestion.law_reader import LawReader
from logging_config import setup_logging

logger = logging.getLogger(__name__)

_DATA_PATH = Path("raw_data/laws/ChLaw.json")


def _log_stats(laws: list[Law]) -> None:
    """記錄法律、條文與引用關係的數量統計。

    Args:
        laws (list[Law]): 已完成引用解析的法律清單。
    """
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
    logger.info(f"法律數量：{len(laws)} 部")
    logger.info(f"條文數量：{total_articles} 條")
    logger.info(f"引用關係：{total_citations} 筆")


def _find_sample(
    laws: list[Law],
) -> tuple[str, str, str] | None:
    """找第一個有引用關係的條文。

    Args:
        laws (list[Law]): 已完成引用解析的法律清單。

    Returns:
        tuple[str, str, str] | None: (law_name, pcode, article_no)，
            找不到時回傳 None。
    """
    for law in laws:
        for article in law.articles:
            has_cite = (
                article.article_type == "A"
                and article.cited_articles
            )
            if has_cite:
                return law.law_name, article.pcode, article.article_no
    return None


def _log_graph_demo(
    laws: list[Law], graph: NxLawGraph
) -> None:
    """記錄圖查詢示範：條文數量、引用與被引用關係。

    Args:
        laws (list[Law]): 已完成引用解析的法律清單。
        graph (NxLawGraph): 已建立的法規圖。
    """
    sample = _find_sample(laws)
    if not sample:
        logger.info("找不到有引用關係的條文")
        return

    law_name, pcode, article_no = sample
    articles = graph.get_law_articles(pcode)
    cited = graph.get_cited_articles(pcode, article_no)
    citing = graph.get_citing_articles(pcode, article_no)

    logger.info(f"--- 圖查詢示範：{law_name} ---")
    logger.info(f"該法共 {len(articles)} 條條文")
    logger.info(f"{article_no} 引用 {len(cited)} 條：")
    for c in cited[:5]:
        logger.info(f"  → {c}")
    logger.info(f"{article_no} 被引用 {len(citing)} 次")


def main() -> None:
    """載入法律資料、解析引用、建圖並記錄示範結果。"""
    setup_logging()
    logger.info("載入法律資料...")
    reader = LawReader(_DATA_PATH)
    laws = reader.load()

    logger.info("解析條文引用...")
    lookup = reader.build_name_to_pcode(laws)
    extractor = CitationExtractor(lookup)
    for law in laws:
        extractor.extract_from_law(law)

    _log_stats(laws)

    logger.info("建立圖結構...")
    graph = LawGraphBuilder().build(laws)
    _log_graph_demo(laws, graph)


if __name__ == "__main__":
    main()
