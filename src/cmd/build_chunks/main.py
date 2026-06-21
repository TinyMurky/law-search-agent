import argparse
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from ingestion.law_graph.builder import LawGraphBuilder
from ingestion.law_ingestion.citation_extractor import CitationExtractor
from ingestion.law_ingestion.law import Law
from ingestion.law_ingestion.law_reader import LawReader
from ingestion.law_vector.chunk_builder import ChunkBuilder
from logging_config import setup_logging

logger = logging.getLogger(__name__)

_DATA_PATH = Path("raw_data/laws/ChLaw.json")
_CHROMA_DIR = "data/chroma_db"
_SAMPLE_QUERY = "侵權行為損害賠償責任"


def _load_laws() -> list[Law]:
    """載入並解析法律資料，包含條文引用關係。

    Returns:
        list[Law]: 已完成引用解析的法律清單。
    """
    logger.info("載入法律資料...")
    reader = LawReader(_DATA_PATH)
    laws = reader.load()
    logger.info("解析條文引用...")
    lookup = reader.build_name_to_pcode(laws)
    extractor = CitationExtractor(lookup)
    for law in laws:
        extractor.extract_from_law(law)
    return laws


def _build_graph(laws: list[Law]) -> None:
    """以法律清單建立 NetworkX 圖結構（僅供本範例展示）。

    Args:
        laws (list[Law]): 已載入的法律清單。
    """
    logger.info("建立圖結構...")
    LawGraphBuilder().build(laws)
    logger.info("圖結構建立完成")


def _build_chunks(builder: ChunkBuilder, laws: list[Law], force: bool) -> int:
    """將法律條文 embed 並存入 Chroma，視 force 決定是否清空重建。

    Args:
        builder (ChunkBuilder): Chroma chunks collection 的建立與
            查詢物件。
        laws (list[Law]): 要建立索引的法律清單。
        force (bool): True 時先清除舊資料再重新 embed。

    Returns:
        int: 本次新增的條文數量。
    """
    if force:
        logger.info("清除舊資料並重新建立 chunks...")
        builder.clear()
    current = builder.count()
    if current > 0:
        logger.info(f"繼續建立 chunks（目前 {current} 筆）...")
    else:
        logger.info("建立 chunks...")
    t0 = time.time()
    added = builder.build(laws, batch_sleep=2.0)
    elapsed = time.time() - t0
    total = builder.count()
    logger.info(f"新增 {added} 筆，總計 {total} 筆，" f"耗時 {elapsed:.1f} 秒")
    return added


def _log_peek(builder: ChunkBuilder) -> None:
    """記錄 Chroma 內的條文樣本，供人工確認資料正確性。

    Args:
        builder (ChunkBuilder): Chroma chunks collection 的查詢物件。
    """
    logger.info("--- Chroma 內的條文樣本 ---")
    for chunk in builder.peek_chunks(3):
        preview = chunk.to_document()[:60].replace("\n", " ")
        logger.info(f"id: {chunk.to_node_id()}  {preview}...")


def _log_search(builder: ChunkBuilder) -> None:
    """以範例查詢示範語意搜尋結果。

    Args:
        builder (ChunkBuilder): Chroma chunks collection 的查詢物件。
    """
    logger.info(f"--- 語意搜尋：「{_SAMPLE_QUERY}」---")
    results = builder.search_chunks(_SAMPLE_QUERY, k=5)
    for i, chunk in enumerate(results, 1):
        score = chunk.score or 0.0
        preview = chunk.artical_content[:60].replace("\n", " ")
        logger.info(
            f"{i}. [{chunk.law_name}] {chunk.article_no}"
            f"  score={score:.4f}  {preview}..."
        )


def main() -> None:
    """執行完整流程：載入法律、建圖、建立並查詢 Chroma chunks。"""
    setup_logging()
    load_dotenv()
    parser = argparse.ArgumentParser(
        description="建立 Chroma chunks collection"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="清除舊資料並重新 embed",
    )
    args = parser.parse_args()

    laws = _load_laws()
    _build_graph(laws)

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    # 以後要作 multimodal embedding 可以升到 002
    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=api_key,
    )
    builder = ChunkBuilder(
        persist_directory=_CHROMA_DIR,
        embeddings=embeddings,
    )
    _build_chunks(builder, laws, force=args.force)
    _log_peek(builder)
    _log_search(builder)


if __name__ == "__main__":
    main()
