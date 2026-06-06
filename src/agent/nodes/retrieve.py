from __future__ import annotations

from collections.abc import Callable
from typing import cast

from langchain_core.documents import Document

from agent.state import AgenticRAGState
from ingestion.law_graph.nodes import ArticleNodeAttrs
from ingestion.law_graph.nx_law_graph import NxLawGraph
from ingestion.law_vector.chunk_builder import ChunkBuilder

_SEARCH_K = 5
_EXPAND_K = 3


# ── Document 轉換 ─────────────────────────────────────────────────────

def _search_result_to_doc(r: dict[str, object]) -> Document:
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
        },
    )


def _article_node_to_doc(
    node_id: str,
    article: ArticleNodeAttrs,
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
                for r in chunk_builder.search(
                    sub["query"], k=_SEARCH_K
                ):
                    _add(_search_result_to_doc(r))

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
                node_id = f"{pcode}#{sub['article_no']}"
                node = law_graph.get_node(node_id)
                if node is None or node["type"] != "article":
                    print(f"[retrieve] 找不到條文：{node_id}")
                    continue
                _add(_article_node_to_doc(
                    node_id, cast(ArticleNodeAttrs, node)
                ))

            elif strategy == "law:graph_expand":
                results = chunk_builder.search(
                    sub["query"], k=_SEARCH_K
                )
                for r in results:
                    _add(_search_result_to_doc(r))
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
                            ))

            elif strategy == "judgment:tavily":
                print("[retrieve] judgment:tavily（placeholder）")

        print(f"[retrieve] 共取得 {len(all_docs)} 份文件")
        return {"documents": all_docs}

    return retrieve_node
