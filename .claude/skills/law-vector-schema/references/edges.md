# `edges` Collection（Phase 1：模板；Phase 2：citation context）

**用途：** 回答「A 和 B 的關係是什麼？」
命中後透過 metadata 的 `source_node_id` / `target_node_id`
從 `chunks` collection 取回兩端條文內容。

---

## Phase 1 — 模板描述

### Document 格式

```
document : f"{source_law} {source_article_no} 引用 "
           f"{target_law} {target_article_no}（{citation_type}）"
           # e.g. "民法 第 184 條 引用 民法 第 185 條（bare）"

id       : f"{source_node_id}→{target_node_id}"

metadata : {
    "source_node_id"   : "B0000001#第 184 條",
    "target_node_id"   : "B0000001#第 185 條",
    "citation_type"    : "bare",
    "source_pcode"     : "B0000001",
    "source_article_no": "第 184 條",
}
```

### Ingestion 範例

```python
def build_edges(laws: list[Law], col: Chroma) -> None:
    pcode_to_name = {law.pcode: law.law_name for law in laws}
    docs, ids, metadatas = [], [], []
    for law in laws:
        for article in law.articles:
            if article.article_type != "A":
                continue
            src_id = f"{article.pcode}#{article.article_no}"
            for cited_id, citation_type in article.cited_articles:
                parts = cited_id.split("#", 1)
                if len(parts) != 2:
                    continue
                tgt_pcode, tgt_article_no = parts
                tgt_law = pcode_to_name.get(tgt_pcode, tgt_pcode)
                docs.append(
                    f"{article.law_name} {article.article_no} 引用 "
                    f"{tgt_law} {tgt_article_no}（{citation_type}）"
                )
                ids.append(f"{src_id}→{cited_id}")
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

## Phase 2 — Citation Context（升級，取代模板）

### Document 格式

```
document : 來源條文中包含引用的那一句話
           # e.g. "違反前條規定者，依第一百八十五條負連帶賠償責任。"

metadata : 與 Phase 1 完全相同，不需修改
```

> **升級前置條件：** `CitationExtractor` 需補充 span 資訊
> （regex match 的字元位置），才能從條文原文截取 citation context 句子。

---

## 命中 Edge 後取兩端節點

```python
def search_relationships(query: str, k: int = 3) -> list[dict]:
    edge_results = edges_col.similarity_search_with_score(query, k=k)
    output = []
    for doc, score in edge_results:
        meta = doc.metadata
        src_docs = chunks_col.get(ids=[meta["source_node_id"]])
        tgt_docs = chunks_col.get(ids=[meta["target_node_id"]])
        output.append({
            "edge_description": doc.page_content,
            "citation_type": meta["citation_type"],
            "source": {
                "node_id": meta["source_node_id"],
                "content": src_docs["documents"][0]
                           if src_docs["documents"] else "",
            },
            "target": {
                "node_id": meta["target_node_id"],
                "content": tgt_docs["documents"][0]
                           if tgt_docs["documents"] else "",
            },
            "score": score,
        })
    return output
```
