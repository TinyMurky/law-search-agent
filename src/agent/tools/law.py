from typing import cast

from langchain_core.tools import BaseTool, tool

from ingestion.law_graph.nodes import ArticleNodeAttrs
from ingestion.law_graph.nx_law_graph import NxLawGraph
from ingestion.law_vector.chunk_builder import ChunkBuilder

_SEP = "\n---\n"


def make_law_tools(
    chunk_builder: ChunkBuilder,
    law_graph: NxLawGraph,
) -> list[BaseTool]:
    """Build law search tools with injected DB dependencies."""

    @tool
    def search_law_articles(query: str) -> str:
        """語意搜尋法條，找與查詢概念最相關的條文。"""
        results = chunk_builder.search_chunks(query, k=5)
        if not results:
            return "找不到相關條文。"
        parts = [
            f"【{r.law_name} {r.article_no}】\n{r.artical_content}"
            for r in results
        ]
        return _SEP.join(parts)

    @tool
    def get_related_articles(pcode: str, article_no: str) -> str:
        """取得條文的引用關係（此條引用哪些條、哪些條引用此條）。"""
        cited = law_graph.get_cited_with_edges(pcode, article_no)
        citing = law_graph.get_citing_with_edges(pcode, article_no)
        lines: list[str] = []
        if cited:
            lines.append("【此條引用的條文】")
            for node_id, edge in cited:
                node = law_graph.get_node(node_id)
                content = (
                    node["content"]  # type: ignore[typeddict-item]
                    if node is not None
                    else ""
                )
                ctype = edge["citation_type"]
                lines.append(f"  {node_id} ({ctype})\n  {content}")
        if citing:
            lines.append("【引用此條的條文】")
            for node_id, _ in citing:
                lines.append(f"  {node_id}")
        if not lines:
            return "此條文無引用關係。"
        return "\n".join(lines)

    @tool
    def get_law_articles(pcode: str) -> str:
        """列出某部法律的所有條文 ID，可再用 get_article 查詢個別條文內容。"""
        article_ids = law_graph.get_law_articles(pcode)
        if not article_ids:
            return f"找不到 pcode={pcode} 的條文。"
        total = len(article_ids)
        listed = "\n".join(article_ids[:50])
        suffix = f"\n（共 {total} 條）" if total > 50 else f"\n（共 {total} 條）"
        return listed + suffix

    @tool
    def get_article(pcode: str, article_no: str) -> str:
        """取得單一條文的完整內容。article_no 格式如「第 184 條」。"""
        node_id = f"{pcode}#{article_no}"
        node = law_graph.get_node(node_id)
        if node is None or node["type"] != "article":
            return f"找不到條文：{node_id}"
        article = cast(ArticleNodeAttrs, node)
        return (
            f"【{article['law_name']} {article['article_no']}】\n"
            f"{article['content']}"
        )

    return [
        search_law_articles,
        get_related_articles,
        get_law_articles,
        get_article,
    ]
