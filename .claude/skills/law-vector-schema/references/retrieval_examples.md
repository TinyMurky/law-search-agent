# Vector DB 互動範例

## 初始化

```python
from langchain_chroma import Chroma
from langchain_google_genai import GoogleGenerativeAIEmbeddings

embeddings = GoogleGenerativeAIEmbeddings(
    model="models/text-embedding-004"
)

chunks_col = Chroma(
    collection_name="chunks",
    persist_directory="./chroma_db",
    embedding_function=embeddings,
)
nodes_col = Chroma(
    collection_name="nodes",
    persist_directory="./chroma_db",
    embedding_function=embeddings,
)
edges_col = Chroma(
    collection_name="edges",
    persist_directory="./chroma_db",
    embedding_function=embeddings,
)
```

---

## 建立 Collections（Ingestion）

```python
from ingestion.law_ingestion.law import Law
from ingestion.law_graph.nx_law_graph import NxLawGraph

def build_chunks(laws: list[Law], col: Chroma) -> None:
    """Article 全文寫入 chunks collection。"""
    docs, ids, metadatas = [], [], []
    for law in laws:
        for article in law.articles:
            if article.article_type != "A":
                continue
            node_id = f"{article.pcode}#{article.article_no}"
            docs.append(
                f"{article.law_name} {article.article_no}\n"
                f"{article.artical_content}"
            )
            ids.append(node_id)
            metadatas.append({
                "pcode": article.pcode,
                "article_no": article.article_no,
                "law_name": article.law_name,
                "law_modified_date": law.law_modified_date,
            })
    col.add_texts(texts=docs, ids=ids, metadatas=metadatas)


def build_nodes_law(laws: list[Law], col: Chroma) -> None:
    """Law 節點描述寫入 nodes collection。"""
    docs, ids, metadatas = [], [], []
    for law in laws:
        docs.append(
            f"{law.law_name}：{law.law_category}，"
            f"位階：{law.law_level}"
        )
        ids.append(law.pcode)
        metadatas.append({
            "pcode": law.pcode,
            "law_name": law.law_name,
            "law_level": law.law_level,
            "law_category": law.law_category,
            "law_modified_date": law.law_modified_date,
        })
    col.add_texts(texts=docs, ids=ids, metadatas=metadatas)


def build_edges(laws: list[Law], col: Chroma) -> None:
    """CITES 邊寫入 edges collection（Phase 1 模板版）。"""
    # 建立 pcode → law_name 的 lookup
    pcode_to_name = {law.pcode: law.law_name for law in laws}

    docs, ids, metadatas = [], [], []
    for law in laws:
        for article in law.articles:
            if article.article_type != "A":
                continue
            src_id = f"{article.pcode}#{article.article_no}"
            src_law = article.law_name

            for cited_id, citation_type in article.cited_articles:
                # cited_id 格式："{pcode}#{article_no}"
                parts = cited_id.split("#", 1)
                if len(parts) != 2:
                    continue
                tgt_pcode, tgt_article_no = parts
                tgt_law = pcode_to_name.get(tgt_pcode, tgt_pcode)

                edge_id = f"{src_id}→{cited_id}"
                docs.append(
                    f"{src_law} {article.article_no} 引用 "
                    f"{tgt_law} {tgt_article_no}（{citation_type}）"
                )
                ids.append(edge_id)
                metadatas.append({
                    "source_node_id": src_id,
                    "target_node_id": cited_id,
                    "citation_type": citation_type,
                    "source_pcode": article.pcode,
                    "source_article_no": article.article_no,
                })
    col.add_texts(texts=docs, ids=ids, metadatas=metadatas)
```

---

## 語意搜尋：Chunk（找相關條文）

```python
def search_articles(query: str, k: int = 5) -> list[dict]:
    results = chunks_col.similarity_search_with_score(query, k=k)
    return [
        {
            "node_id": doc.metadata["pcode"]
                       + "#"
                       + doc.metadata["article_no"],
            "law_name": doc.metadata["law_name"],
            "article_no": doc.metadata["article_no"],
            "content": doc.page_content,
            "score": score,
        }
        for doc, score in results
    ]
```

---

## 語意搜尋：Node Law（找相關法律）

```python
def search_laws(query: str, k: int = 3) -> list[dict]:
    results = nodes_col.similarity_search_with_score(
        query,
        k=k,
        filter={"law_level": "法律"},  # 只搜 Law 節點
    )
    return [
        {
            "pcode": doc.metadata["pcode"],
            "law_name": doc.metadata["law_name"],
            "law_category": doc.metadata["law_category"],
            "score": score,
        }
        for doc, score in results
    ]
```

---

## 語意搜尋：Edge（找兩節點關係，並取回兩端節點）

```python
def search_relationships(
    query: str,
    k: int = 3,
) -> list[dict]:
    """
    命中 edge 後，自動從 chunks collection 取回兩端條文內容。
    用於回答「A 和 B 之間有什麼關係？」
    """
    edge_results = edges_col.similarity_search_with_score(query, k=k)
    output = []
    for doc, score in edge_results:
        meta = doc.metadata
        src_id = meta["source_node_id"]
        tgt_id = meta["target_node_id"]

        # 從 chunks collection 取兩端完整條文
        src_docs = chunks_col.get(ids=[src_id])
        tgt_docs = chunks_col.get(ids=[tgt_id])

        src_content = (
            src_docs["documents"][0] if src_docs["documents"] else ""
        )
        tgt_content = (
            tgt_docs["documents"][0] if tgt_docs["documents"] else ""
        )

        output.append({
            "edge_description": doc.page_content,
            "citation_type": meta["citation_type"],
            "source": {"node_id": src_id, "content": src_content},
            "target": {"node_id": tgt_id, "content": tgt_content},
            "score": score,
        })
    return output
```

---

## 語意搜尋後繼續走圖

```python
from ingestion.law_graph.nx_law_graph import NxLawGraph

def search_and_expand(
    query: str,
    graph: NxLawGraph,
    k: int = 3,
) -> dict:
    """
    1. 語意搜尋找到最相關條文
    2. 繼續走圖取引用關係
    """
    hits = search_articles(query, k=k)
    result = []
    for hit in hits:
        pcode = hit["node_id"].split("#")[0]
        article_no = hit["node_id"].split("#", 1)[1]
        cited = graph.get_cited_articles(pcode, article_no)
        citing = graph.get_citing_articles(pcode, article_no)
        result.append({
            **hit,
            "cited_articles": cited,
            "citing_articles": citing,
        })
    return result
```

---

## 在 LangGraph Tool 中使用

```python
from langchain_core.tools import tool

@tool
def search_law_articles(query: str) -> str:
    """語意搜尋法律條文內容。"""
    hits = search_articles(query, k=5)
    lines = []
    for h in hits:
        lines.append(
            f"【{h['law_name']} {h['article_no']}】\n{h['content']}"
        )
    return "\n\n".join(lines)


@tool
def search_laws(query: str) -> str:
    """語意搜尋相關法律（返回法律名稱與 pcode）。"""
    hits = search_laws(query, k=3)
    lines = [
        f"{h['law_name']}（{h['pcode']}）- {h['law_category']}"
        for h in hits
    ]
    return "\n".join(lines)
```
