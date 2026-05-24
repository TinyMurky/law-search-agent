# `communities` Collection（Phase 2）

**用途：** 回答高層次抽象查詢，例如「侵權行為的法律機制有哪些？」
條文層級的搜尋很難回答這類問題；社群摘要提供跨條文的整體視角。

---

## Document 格式

```
document : LLM 對該社群的法律語意摘要
           # e.g. "此群條文處理民法侵權行為責任，包含一般侵權（第184條）、
           #       共同侵權（第185條）、法定代理人責任（第187條）等規定"

id       : f"community_{community_id}"

metadata : {
    "community_id" : 0,
    "node_ids"     : ["B0000001#第 184 條", "B0000001#第 185 條", ...],
    "pcode_list"   : ["B0000001"],
    "size"         : 12,   # 社群內節點數
}
```

---

## 建立流程

```
1. NxLawGraph 建好後，用 NetworkX community detection 分群
2. 對每個社群，將群內條文全文送給 Gemini 生成摘要
3. 摘要寫入 communities collection
```

```python
import networkx as nx
from networkx.algorithms import community

def detect_communities(G: nx.DiGraph) -> list[frozenset]:
    # 只考慮 CITES 邊做分群
    cites_graph = nx.Graph([
        (u, v) for u, v, d in G.edges(data=True)
        if d.get("relation") == "cites"
    ])
    return list(
        community.greedy_modularity_communities(cites_graph)
    )
```

---

## 連回 Graph

```python
# 命中社群後，透過 node_ids 批次取條文
node_ids = meta["node_ids"]
docs = chunks_col.get(ids=node_ids)

# 或直接走圖取每個節點的引用關係
for node_id in node_ids:
    pcode, article_no = node_id.split("#", 1)
    cited = graph.get_cited_articles(pcode, article_no)
```
