from __future__ import annotations

import logging
import os
import sys

from dotenv import load_dotenv
from langchain_google_genai import (
    ChatGoogleGenerativeAI,
    GoogleGenerativeAIEmbeddings,
)
from langgraph.graph.state import CompiledStateGraph

from agent.graph import build_graph
from ingestion.law_graph.builder import LawGraphBuilder
from ingestion.law_graph.nx_law_graph import NxLawGraph
from ingestion.law_ingestion.citation_extractor import CitationExtractor
from ingestion.law_ingestion.law_reader import LawReader
from ingestion.law_vector.chunk_builder import ChunkBuilder

logger = logging.getLogger(__name__)

_RAW_DATA = "raw_data/laws/ChLaw.json"
_CHROMA_DIR = "data/chroma_db"
_LLM_MODEL = "gemini-3.5-flash"
_EMBEDDING_MODEL = "models/gemini-embedding-001"


def _load_law_graph_and_chunks(
    api_key: str | None,
) -> tuple[ChunkBuilder, NxLawGraph]:
    """載入法規資料、建立圖結構與 Chroma chunk_builder。

    Args:
        api_key (str | None): Gemini API key，傳入 embedding 模型。

    Returns:
        tuple[ChunkBuilder, NxLawGraph]: 向量搜尋與圖查詢依賴。
    """
    logger.info("載入法規資料中...")
    reader = LawReader(_RAW_DATA)
    laws = reader.load()
    extractor = CitationExtractor(reader.build_name_to_pcode(laws))
    for law in laws:
        extractor.extract_from_law(law)
    law_graph = LawGraphBuilder().build(laws)
    logger.info(f"圖建立完成（{len(laws)} 部法律）")

    embeddings = GoogleGenerativeAIEmbeddings(
        model=_EMBEDDING_MODEL,
        google_api_key=api_key,
    )
    chunk_builder = ChunkBuilder(_CHROMA_DIR, embeddings)
    return chunk_builder, law_graph


def _ensure_chunks_built(builder: ChunkBuilder) -> None:
    """Chroma 未建立時記錄錯誤並中止整個程式。

    供所有 entry point 共用的 fail-fast 檢查：沒有 chunks 的話
    Agent 不可能正常運作，啟動時就應該直接中止，而不是等到第一個
    請求才發現查不到任何文件。

    Args:
        builder (ChunkBuilder): 用於檢查是否已建立 chunks 的物件。
    """
    if not builder.is_populated():
        logger.error("Chroma DB 尚未建立，請先執行：make build-chunks")
        sys.exit(1)


def build_agent_from_env() -> CompiledStateGraph:
    """讀取 .env、建立所有依賴並組裝編譯完成的 Self-RAG LangGraph。

    供 chat、api_server、mcp_server 等 entry point 共用，避免各自
    複製一份「讀環境變數、建圖、建 Chroma、組 Agent」的邏輯。

    Returns:
        CompiledStateGraph: 已編譯、可直接 invoke 的 LangGraph。
    """
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    chunk_builder, law_graph = _load_law_graph_and_chunks(api_key)
    _ensure_chunks_built(chunk_builder)

    llm = ChatGoogleGenerativeAI(
        model=_LLM_MODEL,
        google_api_key=api_key,
    )
    return build_graph(llm, chunk_builder, law_graph)
