from __future__ import annotations

import re
from collections.abc import Callable
from typing import cast

from langchain_core.documents import Document

from agent.state import AgenticRAGState
from ingestion.law_graph.nodes import ArticleNodeAttrs
from ingestion.law_graph.nx_law_graph import NxLawGraph
from ingestion.law_vector.article_chunk import ArticleChunk
from ingestion.law_vector.chunk_builder import ChunkBuilder

# VectorDB 會搜出幾個結果
_SEARCH_K = 5

# 法條的引用對象只會拿最前面 k 個
_EXPAND_K = 10


def _normalize_article_no(raw: str) -> str:
    """第184條 / 第184条 → 第 184 條（符合圖裡的 node_id 格式）"""
    s = re.sub(r"\s+", "", raw)
    return re.sub(r"^第(\d+)[條条]$", r"第 \1 條", s)


# ── Document 轉換 ─────────────────────────────────────────────────────
# metadata 中的 "strategy" 欄位供 grade_documents 查詢 STRATEGY_REGISTRY。
# ( 在 src/agent/STRATEGY_REGISTRY, 可查詢 required_grading )
# retrieve 本身的各 strategy 分支（if/elif）目前維持在此處，
# 未來可將各分支的 retriever 邏輯封裝進 STRATEGY_REGISTRY 的欄位遷出。


def _search_result_to_doc(
    chunk: ArticleChunk,
    strategy: str,
) -> Document:
    """
    將 vectorDB 取出的 ArticleChunk 轉成 llm 原生的 Document type
    """
    return Document(
        page_content=(chunk.to_document()),
        metadata={
            "node_id": chunk.to_node_id(),
            "pcode": chunk.pcode,
            "article_no": chunk.article_no,
            "law_name": chunk.law_name,
            "source": "law",
            "strategy": strategy,
        },
    )


def _article_node_to_doc(
    node_id: str,
    article: ArticleNodeAttrs,
    strategy: str,
) -> Document:
    law = article["law_name"]
    no = article["article_no"]
    body = article["content"]
    return Document(
        page_content=f"{law} {no}\n{body}",
        metadata={
            "node_id": node_id,
            "pcode": article["pcode"],
            "article_no": article["article_no"],
            "law_name": article["law_name"],
            "source": "law",
            "strategy": strategy,
        },
    )


# ── Node factory ──────────────────────────────────────────────────────


def make_retrieve_node(
    chunk_builder: ChunkBuilder,
    law_graph: NxLawGraph,
) -> Callable[[AgenticRAGState], dict[str, object]]:
    """建立 retrieve 節點，注入 DB 依賴。"""

    def retrieve_node(
        state: AgenticRAGState,
    ) -> dict[str, object]:
        all_docs: list[Document] = []
        seen: set[str] = set()

        def _add(doc: Document) -> None:
            nid = str(doc.metadata["node_id"])
            if nid not in seen:
                seen.add(nid)
                all_docs.append(doc)

        for sub in state["rewritten_queries"]:
            strategy = sub["strategy"]
            print(f"[retrieve] strategy={strategy}")

            if strategy in ("law:semantic", "law:hyde"):
                try:
                    results = chunk_builder.search_chunks(
                        sub["query"],
                        k=_SEARCH_K,
                    )
                except Exception as e:
                    print(f"[retrieve] embedding 錯誤，跳過：{e}")
                    continue
                for chunk in results:
                    _add(_search_result_to_doc(chunk, strategy))

            elif strategy in (
                "law:direct_lookup",
                "law:direct_lookup_ambiguous",
            ):
                pcode = law_graph.find_pcode_by_name(sub["law_name"] or "")
                if pcode is None:
                    print(f"[retrieve] 找不到 pcode：{sub['law_name']}")
                    continue
                article_no = _normalize_article_no(sub["article_no"] or "")
                result = law_graph.get_article(pcode, article_no)
                if result is None:
                    print(f"[retrieve] 找不到條文：" f"{pcode}#{article_no}")
                    continue
                node_id, article = result
                _add(_article_node_to_doc(node_id, article, strategy))

            elif strategy == "law:graph_expand":
                try:
                    results = chunk_builder.search_chunks(
                        sub["query"],
                        k=_SEARCH_K,
                    )
                except Exception as e:
                    print(f"[retrieve] embedding 錯誤，跳過：{e}")
                    continue
                for chunk in results:
                    _add(_search_result_to_doc(chunk, strategy))
                    cited = law_graph.get_cited_with_edges(
                        chunk.pcode,
                        chunk.article_no,
                    )
                    for cited_law_node_id, _ in cited[:_EXPAND_K]:
                        cited_node = law_graph.get_node(cited_law_node_id)
                        if cited_node is None:
                            continue
                        if cited_node["type"] == "article":
                            _add(
                                _article_node_to_doc(
                                    cited_law_node_id,
                                    # 這邊先暫時這樣, 之後可以改成有更細節的專門 get_artical_node
                                    cast(ArticleNodeAttrs, cited_node),
                                    strategy,
                                )
                            )

            elif strategy == "judgment:tavily":
                print("[retrieve] judgment:tavily（placeholder）")

        print(f"[retrieve] 共取得 {len(all_docs)} 份文件")
        return {"documents": all_docs}

    return retrieve_node
