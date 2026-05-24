import argparse
import time
from pathlib import Path

from dotenv import load_dotenv
from langchain_google_genai import GoogleGenerativeAIEmbeddings

from ingestion.law_graph.builder import LawGraphBuilder
from ingestion.law_ingestion.citation_extractor import (
    CitationExtractor,
)
from ingestion.law_ingestion.law import Law
from ingestion.law_ingestion.law_reader import LawReader
from ingestion.law_vector.chunk_builder import ChunkBuilder

_DATA_PATH = Path("raw_data/laws/ChLaw.json")
_CHROMA_DIR = "data/chroma_db"
_SAMPLE_QUERY = "侵權行為損害賠償責任"


def _load_laws() -> list[Law]:
    print("載入法律資料...")
    reader = LawReader(_DATA_PATH)
    laws = reader.load()
    print("解析條文引用...")
    lookup = reader.build_name_to_pcode(laws)
    extractor = CitationExtractor(lookup)
    for law in laws:
        extractor.extract_from_law(law)
    return laws


def _build_graph(laws: list[Law]) -> None:
    print("\n建立圖結構...")
    LawGraphBuilder().build(laws)
    print("圖結構建立完成")


def _build_chunks(
    builder: ChunkBuilder, laws: list[Law], force: bool
) -> int:
    if builder.is_populated() and not force:
        n = builder.count()
        print(f"使用已存在的 chunks（{n} 筆），跳過建立")
        return n
    if force:
        print("清除舊資料並重新建立 chunks...")
        builder.clear()
    else:
        print("建立 chunks...")
    t0 = time.time()
    n = builder.build(laws)
    elapsed = time.time() - t0
    print(f"完成：{n} 筆 chunk，耗時 {elapsed:.1f} 秒")
    return n


def _print_peek(builder: ChunkBuilder) -> None:
    print("\n--- Chroma 內的條文樣本 ---")
    for row in builder.peek(3):
        print(f"id: {row['id']}")
        doc = str(row["document"])
        preview = doc[:60].replace("\n", " ")
        print(f"  {preview}...")
        print()


def _print_search(builder: ChunkBuilder) -> None:
    print(f"\n--- 語意搜尋：「{_SAMPLE_QUERY}」---")
    results = builder.search(_SAMPLE_QUERY, k=5)
    for i, r in enumerate(results, 1):
        name = r["law_name"]
        no = r["article_no"]
        score = r["score"]
        print(f"{i}. [{name}] {no}  score={score:.4f}")
        content = str(r["content"])
        preview = content[:60].replace("\n", " ")
        print(f"   {preview}...")


def main() -> None:
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

    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/text-embedding-004"
    )
    builder = ChunkBuilder(
        persist_directory=_CHROMA_DIR,
        embeddings=embeddings,
    )
    _build_chunks(builder, laws, force=args.force)
    _print_peek(builder)
    _print_search(builder)


if __name__ == "__main__":
    main()
