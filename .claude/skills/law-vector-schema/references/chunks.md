# `chunks` Collection（Phase 1）

**用途：** 回答「找和 X 概念有關的條文」，最基本的條文語意搜尋。
加 header（法律名稱 + 條號）讓 embedding 含法律脈絡，避免跨法律語意混淆。

## Document 格式

```
document : f"{law_name} {article_no}\n{content}"
           # e.g. "民法 第 184 條\n因故意或過失，不法侵害他人之權利者…"

id       : f"{pcode}#{article_no}"
           # 與 NxLawGraph 的 node_id 格式相同，可直接走圖

metadata : {
    "pcode"             : "B0000001",
    "article_no"        : "第 184 條",
    "law_name"          : "民法",
    "law_modified_date" : "20240101",
}
```

## 連回 Graph

```python
node_id = f"{meta['pcode']}#{meta['article_no']}"
graph.get_cited_articles(meta["pcode"], meta["article_no"])
graph.get_citing_articles(meta["pcode"], meta["article_no"])
```

## Ingestion 範例

```python
def build_chunks(laws: list[Law], col: Chroma) -> None:
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
```

## 搜尋範例

```python
def search_articles(query: str, k: int = 5) -> list[dict]:
    results = chunks_col.similarity_search_with_score(query, k=k)
    return [
        {
            "node_id": f"{doc.metadata['pcode']}"
                       f"#{doc.metadata['article_no']}",
            "law_name": doc.metadata["law_name"],
            "article_no": doc.metadata["article_no"],
            "content": doc.page_content,
            "score": score,
        }
        for doc, score in results
    ]
```
