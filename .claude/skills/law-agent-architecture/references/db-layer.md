# DB Layer

## 兩種查詢需求，兩種資料庫

法律資料有兩種完全不同的查詢方式：

| 查詢類型 | 例子 | 用什麼 |
|---|---|---|
| **語意查詢** | 「有什麼法條保護消費者？」 | Vector DB（Chroma） |
| **結構查詢** | 「民法第184條引用了哪些條文？」 | Graph DB（NetworkX） |

兩者透過 `node_id`（格式：`{pcode}#{article_no}`，例如 `B0000001#第 184 條`）串接：
語意搜尋命中條文 → 從 metadata 取出 node_id → 交給 Graph DB 走引用關係。

---

## Phase 1：Chroma（Vector）+ NetworkX（Graph）

### 目前實作狀態

| 元件 | 狀態 | 程式碼位置 |
|---|---|---|
| Chroma `chunks` collection | 已完成 | `src/ingestion/law_vector/chunk_builder.py` |
| NetworkX 圖建立 | 已完成 | `src/ingestion/law_graph/builder.py` |
| CLI 入口 | 已完成 | `src/cmd/build_chunks/main.py` |

### Vector DB：Chroma

**職責**：語意搜尋，找「概念相關」的條文

**Collection 設計（chunks）：**

| 欄位 | 說明 | 例子 |
|---|---|---|
| `id` | 條文唯一識別碼 | `B0000001#第 184 條` |
| `document` | 用來 embed 的文字 | `民法 第 184 條\n因故意或過失...` |
| `metadata.pcode` | 法律代號 | `B0000001` |
| `metadata.article_no` | 條文編號 | `第 184 條` |
| `metadata.law_name` | 法律名稱 | `民法` |
| `metadata.law_modified_date` | 法律版本日期 | `20210101` |

**介面合約（ChunkBuilder）：**

| 方法 | 輸入 | 輸出 | 說明 |
|---|---|---|---|
| `build(laws)` | `list[Law]` | `int`（新增筆數） | 嵌入條文，跳過已存在的 |
| `search(query, k=5)` | 自然語言 | `list[dict]` | 語意搜尋，回傳最相關 k 筆 |
| `peek(n=3)` | 數量 | `list[dict]` | 查看前 n 筆（不需要 embed）|
| `count()` | - | `int` | 目前有幾筆 |
| `clear()` | - | - | 清空重建 |

**search 回傳格式：**
```python
[
  {
    "node_id": "B0000001#第 184 條",   # 給 Graph DB 用
    "law_name": "民法",
    "article_no": "第 184 條",
    "content": "因故意或過失...",
    "score": 0.82                       # 相似度分數
  },
  ...
]
```

---

### Graph DB：NetworkX

**職責**：結構查詢，沿著引用關係找相關條文

**節點類型：**

| 節點 | ID 格式 | 說明 |
|---|---|---|
| `Law` | `{pcode}` | 一部法律 |
| `Article` | `{pcode}#{article_no}` | 單一條文 |

**邊類型：**

| 邊 | 從 → 到 | 說明 |
|---|---|---|
| `contains` | Law → Article | 這部法律包含這條條文 |
| `cites` | Article → Article | 這條引用了那條 |

**介面合約（NxLawGraph）：**

API 分三層，Agent tool 直接使用語意層，不需接觸底層。

**語意層（Agent tool 使用）**

| 方法 | 輸入 | 輸出 | 說明 |
|---|---|---|---|
| `get_cited_articles(pcode, article_no)` | 條文編號 | `list[str]` | 此條引用的條文 ID 清單 |
| `get_citing_articles(pcode, article_no)` | 條文編號 | `list[str]` | 引用此條的條文 ID 清單 |
| `get_law_articles(pcode)` | `pcode` | `list[str]` | 此法律的所有條文 ID |
| `get_cited_with_edges(pcode, article_no)` | 條文編號 | `list[tuple[str, CitesEdgeAttrs]]` | 此條引用的條文 + 邊屬性（含 citation_type） |
| `get_citing_with_edges(pcode, article_no)` | 條文編號 | `list[tuple[str, CitesEdgeAttrs]]` | 引用此條的條文 + 邊屬性 |

**節點／邊存取**

| 方法 | 輸入 | 輸出 | 說明 |
|---|---|---|---|
| `get_node(node_id)` | `node_id` | `LawNodeAttrs \| ArticleNodeAttrs \| None` | 取節點屬性，不存在回傳 None |
| `get_edge(u, v)` | 兩端 node_id | `ContainsEdgeAttrs \| CitesEdgeAttrs \| None` | 取邊屬性，不存在回傳 None |

**通用底層（Phase 1.5 新邊類型暫用）**

| 方法 | 輸入 | 輸出 | 說明 |
|---|---|---|---|
| `get_related(node_id, relation, direction)` | relation 字串、方向 | `list[str]` | 語意層尚無對應方法時的通用查詢 |
| `get_neighbors_with_edges(node_id, relation, direction)` | relation 字串、方向 | `list[tuple[str, edge_attrs]]` | 同上，附帶邊屬性 |

**兩層串接範例：**
```
1. Chroma 搜尋「侵權行為損害賠償」
   → 命中 node_id = "B0000001#第 184 條"

2. 把 node_id 傳給 NetworkX
   → 找到引用的 "B0000001#第 185 條"（共同侵權）

3. Agent 把兩筆結果一起整理回答
```

---

## Phase 2：Neo4j（統一取代）

Phase 2 的核心變化：Chroma + NetworkX 兩套系統統一換成一套 Neo4j，
Vector 搜尋和圖遍歷都在同一個資料庫完成。

### 為什麼要換

| 問題 | Phase 1 | Phase 2（Neo4j）|
|---|---|---|
| 系統數量 | 兩套（Chroma + NetworkX） | 一套 |
| NetworkX 持久化 | 不持久（重啟要重算） | 持久化 |
| 向量 + 圖的聯合查詢 | 要在 Python 手動串接 | 一個 Cypher 語句搞定 |
| 生產環境穩定性 | NetworkX 不適合生產環境 | 適合 |

### Phase 2 的介面變化

| 工具 | Phase 1 底層 | Phase 2 底層 |
|---|---|---|
| `search_law_articles` | `ChunkBuilder.search()` | Neo4j 向量索引查詢 |
| `get_related_articles` | `NxLawGraph.get_cited_articles()` | Neo4j Cypher 查詢 |

Agent 的 tool 函式簽名（輸入輸出格式）不變，只是內部換底層。
FastAPI 和 MCP Server 完全感知不到這個變化。

### Phase 2 前置工作

- Neo4j 5.x（支援向量索引）
- 建立 `Article` 節點的向量索引
- 把 NetworkX 的邊資料移入 Neo4j
- 更新 tool 內部的查詢邏輯

詳細的 Neo4j schema 設計參照 `law-graph-schema` skill。
