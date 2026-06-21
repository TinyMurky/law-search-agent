import os
import sys

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_google_genai import (ChatGoogleGenerativeAI,
                                    GoogleGenerativeAIEmbeddings)
from langgraph.graph.state import CompiledStateGraph

from agent.graph import build_graph
from ingestion.law_graph.builder import LawGraphBuilder
from ingestion.law_graph.nx_law_graph import NxLawGraph
from ingestion.law_ingestion.citation_extractor import CitationExtractor
from ingestion.law_ingestion.law_reader import LawReader
from ingestion.law_vector.chunk_builder import ChunkBuilder
from logging_config import setup_logging

_RAW_DATA = "raw_data/laws/ChLaw.json"
_CHROMA_DIR = "data/chroma_db"


def _check_chunks(builder: ChunkBuilder) -> None:
    """Chroma 未建立時提示使用者並中止。

    Args:
        builder (ChunkBuilder): 用於檢查是否已建立 chunks 的物件。
    """
    if not builder.is_populated():
        print("⚠️  Chroma DB 尚未建立，請先執行：")
        print("    make build-chunks")
        sys.exit(1)


def _load_deps(
    api_key: str | None,
) -> tuple[ChunkBuilder, NxLawGraph]:
    """載入法規資料、建立圖結構與 Chroma chunk_builder。

    Args:
        api_key (str | None): Gemini API key，傳入 embedding 模型。

    Returns:
        tuple[ChunkBuilder, NxLawGraph]: 向量搜尋與圖查詢依賴。
    """
    print("載入法規資料中...", flush=True)
    reader = LawReader(_RAW_DATA)
    laws = reader.load()
    extractor = CitationExtractor(reader.build_name_to_pcode(laws))
    for law in laws:
        extractor.extract_from_law(law)
    law_graph = LawGraphBuilder().build(laws)
    print(f"圖建立完成（{len(laws)} 部法律）", flush=True)

    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=api_key,
    )
    chunk_builder = ChunkBuilder(_CHROMA_DIR, embeddings)
    return chunk_builder, law_graph


def _initial_state(question: str) -> dict[str, object]:
    """建立單次對話的初始 AgenticRAGState。

    Args:
        question (str): 使用者輸入的問題。

    Returns:
        dict[str, object]: 可直接傳入 graph.invoke 的初始狀態。
    """
    return {
        "question": question,
        "intent": "",
        "complexity": "",
        "rewritten_queries": [],
        "documents": [],
        "grade_passed": False,
        "generation": "",
        "hallucination_passed": True,
        "answer_passed": True,
        "rewrite_count": 0,
        "max_rewrites": 3,
        "regenerate_count": 0,
        "max_regenerates": 2,
        "halt_reason": "",
        "judgment_api_token": "",
        "messages": [HumanMessage(content=question)],
    }


def _chat_loop(graph: CompiledStateGraph) -> None:
    """啟動互動式對話迴圈，直到使用者輸入 exit。

    Args:
        graph (CompiledStateGraph): 已編譯的 Self-RAG LangGraph。
    """
    print("\n法律搜尋 Agent 已啟動（輸入 exit 離開）\n")
    while True:
        try:
            user_input = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n離開。")
            break
        if user_input.lower() in ("exit", "quit", "q", ""):
            break
        result = graph.invoke(_initial_state(user_input))
        answer = result.get("generation") or ""
        if not answer:
            msgs = result.get("messages", [])
            answer = msgs[-1].content if msgs else "（無回應）"
        print(f"\nAgent: {answer}\n")


def main() -> None:
    """載入依賴、編譯 Graph 並啟動互動式對話迴圈。"""
    setup_logging()
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    chunk_builder, law_graph = _load_deps(api_key)
    _check_chunks(chunk_builder)

    llm = ChatGoogleGenerativeAI(
        model="gemini-3.5-flash",
        google_api_key=api_key,
    )
    graph = build_graph(llm, chunk_builder, law_graph)
    _chat_loop(graph)


if __name__ == "__main__":
    main()
