# `nodes` Collection（Phase 1：Law；Phase 2：Article）

**用途：** 不同粒度的節點查詢。
- **Law**：「哪部法律管這件事？」→ 返回 pcode，再用 `get_law_articles()` 展開
- **Article**（Phase 2）：語意摘要，與 chunks 互補，適合「這條文的核心概念是什麼」

## Phase 1 — Law 節點

### Document 格式

```
document : f"{law_name}：{law_category}，位階：{law_level}"
           # e.g. "民法：民事，位階：法律"

id       : pcode
           # e.g. "B0000001"

metadata : {
    "pcode"             : "B0000001",
    "law_name"          : "民法",
    "law_level"         : "法律",
    "law_category"      : "民事",
    "law_modified_date" : "20240101",
}
```

### 連回 Graph

```python
node_id = meta["pcode"]
graph.get_law_articles(node_id)
```

### Ingestion 範例

```python
def build_nodes_law(laws: list[Law], col: Chroma) -> None:
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
```

### 搜尋範例

```python
def search_laws(query: str, k: int = 3) -> list[dict]:
    results = nodes_col.similarity_search_with_score(
        query, k=k,
        filter={"law_level": "法律"},
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

## Phase 2 — Article 節點（LLM 生成摘要）

### Document 格式

```
document : LLM 生成的條文概念摘要
           # e.g. "本條規定行為人因故意或過失不法侵害他人權利時，
           #       應負損害賠償責任（一般侵權行為）"

id       : f"{pcode}#{article_no}"
           # 加入現有 nodes collection，不另開新 collection

metadata : {
    "pcode"      : "B0000001",
    "article_no" : "第 184 條",
    "law_name"   : "民法",
}
```

### 連回 Graph

```python
node_id = f"{meta['pcode']}#{meta['article_no']}"
graph.get_cited_articles(meta["pcode"], meta["article_no"])
```
