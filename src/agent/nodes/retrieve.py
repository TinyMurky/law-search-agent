from __future__ import annotations

import re
from collections.abc import Callable
from typing import cast

from langchain_core.documents import Document

from agent.state import AgenticRAGState
from ingestion.law_graph.nodes import ArticleNodeAttrs
from ingestion.law_graph.nx_law_graph import NxLawGraph
from ingestion.law_vector.chunk_builder import ChunkBuilder

_SEARCH_K = 5
_EXPAND_K = 3


def _normalize_article_no(raw: str) -> str:
    """第184條 / 第184条 → 第 184 條（符合圖裡的 node_id 格式）"""
    s = re.sub(r"\s+", "", raw)
    return re.sub(r"^第(\d+)[條条]$", r"第 \1 條", s)


# ── Document 轉換 ─────────────────────────────────────────────────────
# metadata 中的 "strategy" 欄位供 grade_documents 查詢 STRATEGY_REGISTRY。
# retrieve 本身的各 strategy 分支（if/elif）目前維持在此處，
# 未來可將各分支的 retriever 邏輯封裝進 STRATEGY_REGISTRY 的欄位遷出。

def _search_result_to_doc(
    r: dict[str, object],
    strategy: str,
) -> Document:
    return Document(
        page_content=(
            f"【{r['law_name']} {r['article_no']}】\n{r['content']}"
        ),
        metadata={
            "node_id": r["node_id"],
            "pcode": cast(str, r["node_id"]).split("#")[0],
            "article_no": r["article_no"],
            "law_name": r["law_name"],
            "source": "law",
            "strategy": strategy,
        },
    )


def _article_node_to_doc(
    node_id: str,
    article: ArticleNodeAttrs,
    strategy: str,
) -> Document:
    return Document(
        page_content=(
            f"【{article['law_name']} {article['article_no']}】\n"
            f"{article['content']}"
        ),
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
                    results = chunk_builder.search(
                        sub["query"], k=_SEARCH_K
                    )
                except Exception as e:
                    print(f"[retrieve] embedding 錯誤，跳過：{e}")
                    continue
                for r in results:
                    _add(_search_result_to_doc(r, strategy))

            elif strategy == "law:direct_lookup":
                pcode = law_graph.find_pcode_by_name(
                    sub["law_name"] or ""
                )
                if pcode is None:
                    print(
                        f"[retrieve] 找不到 pcode："
                        f"{sub['law_name']}"
                    )
                    continue
                article_no = _normalize_article_no(
                    sub["article_no"] or ""
                )
                node_id = f"{pcode}#{article_no}"
                node = law_graph.get_node(node_id)
                if node is None or node["type"] != "article":
                    print(f"[retrieve] 找不到條文：{node_id}")
                    continue
                _add(_article_node_to_doc(
                    node_id,
                    cast(ArticleNodeAttrs, node),
                    strategy,
                ))

            elif strategy == "law:graph_expand":
                try:
                    results = chunk_builder.search(
                        sub["query"], k=_SEARCH_K
                    )
                except Exception as e:
                    print(f"[retrieve] embedding 錯誤，跳過：{e}")
                    continue
                for r in results:
                    _add(_search_result_to_doc(r, strategy))
                    node_id_str = cast(str, r["node_id"])
                    pcode = node_id_str.split("#")[0]
                    article_no = node_id_str.split("#", 1)[1]
                    cited = law_graph.get_cited_with_edges(
                        pcode, article_no
                    )
                    for cited_id, _ in cited[:_EXPAND_K]:
                        cited_node = law_graph.get_node(cited_id)
                        if (
                            cited_node is not None
                            and cited_node["type"] == "article"
                        ):
                            _add(_article_node_to_doc(
                                cited_id,
                                cast(ArticleNodeAttrs, cited_node),
                                strategy,
                            ))

            elif strategy == "judgment:tavily":
                print("[retrieve] judgment:tavily（placeholder）")

        print(f"[retrieve] 共取得 {len(all_docs)} 份文件")
        return {"documents": all_docs}

    return retrieve_node
