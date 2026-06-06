---
name: law-rag-agent
description: >
  法律搜尋 Agent 的 Self-RAG 架構文件。記錄 AgenticRAGState 欄位設計、
  SubQuery 型別、Graph 節點職責、路由條件邊、Intent 分類，
  以及各 Grader 的判斷策略。
  當使用者詢問「agent 怎麼設計」、「節點之間怎麼連接」、「State 有哪些欄位」、
  「grader 怎麼判斷」、「retrieve 依 intent 路由到哪裡」，
  或 AI agent 需要實作 Graph 節點、State、路由邏輯、Grader 時，
  必須先讀此 skill。節點完整程式碼見 references/nodes.md。
  架構有任何設計決策更新，先改此 skill 再動程式碼。
---

# 法律搜尋 Self-RAG Agent 架構

## 設計動機

原架構（`login → agent ⇆ tool → END`）讓 Gemini 自由決定呼叫哪些工具，
缺乏對檢索品質和答案品質的主動控制。

新架構改為帶品質回饋環的 Self-RAG 流程：
- **analyze_query**：依問題類型選擇查詢策略（HyDE / 子查詢 / rewrite）
- **retrieve**：依 SubQuery.strategy 路由到對應資料源
- **grade_documents**：過濾不相關文件，不夠就重查
- **generate**：生成答案
- **幻覺 grader + answer grader**：雙重確保答案品質

---

## Graph 流程

```
           ┌─────────┐
           │  START  │
           └────┬────┘
                │
                ▼
       ┌─────────────────┐
       │   login_node    │  （placeholder，設定 judgment_api_token）
       └────────┬────────┘
                │
                ▼
       ┌─────────────────┐
       │  analyze_query  │
       └────────┬────────┘
                │
                ▼
       ┌─────────────────┐ ◄──────────────────────────────────┐
       │    retrieve     │                                    │
       └────────┬────────┘                                    │
                │                                             │
                ▼                                             │
       ┌─────────────────┐                                    │
       │ grade_documents │                                    │
       └────────┬────────┘                                    │
                │                                             │
       ┌────────┼───────────────┐                             │
       │        │               │                             │
  "generate" "rewrite_query" "force_end"                      │
       │        │               │                             │
       ▼        ▼               ▼                             │
  ┌──────────┐ ┌──────────────┐ ┌───────────┐                │
  │ generate │ │rewrite_query │ │ force_end │                │
  └────┬─────┘ └──────┬───────┘ └─────┬─────┘                │
       │               │              │                       │
       │               └──────────────┴── → retrieve ────────►┘
       │                       force_end → END
       │
       ├── "finish" ──────────────────────────────────────► END
       │
       ├── "regenerate" ──────────────────────────────────┐
       │                                                  ▼
       │                                            ┌──────────┐
       │                                            │ generate │
       │                                            └──────────┘
       │
       └── "rewrite_query" ──────────────────────► rewrite_query
```

---

## SubQuery 與 State 設計

### SubQuery

`strategy` 欄位同時編碼 source（查哪裡）與 method（怎麼查），
避免 source + strategy 分開存放導致無效組合。

```python
class SubQuery(TypedDict):
    query: str
    strategy: Literal[
        "law:semantic",       # Chroma 語意搜尋
        "law:hyde",           # HyDE 再語意搜尋（query 已是假設條文）
        "law:direct_lookup",  # Graph 直接查節點（已知條號）
        "law:graph_expand",   # 語意搜尋 + Graph 遍歷引用鏈
        "judgment:tavily",    # Tavily + 司法院 API（placeholder）
    ]
    law_name: str | None    # 只有 law:direct_lookup 時有值，如「民法」
    article_no: str | None  # 只有 law:direct_lookup 時有值，如「第 184 條」
```

> **設計決策**：用 `"law:semantic"` 字串而非 `tuple["law", "semantic"]`，
> 原因是 LangGraph State 序列化時 tuple 會變成 list，造成型別不穩定。

### AgenticRAGState

```python
class AgenticRAGState(TypedDict):
    # 輸入（整個 Graph 執行期間不變）
    question: str

    # analyze_query 的輸出
    intent: str      # "lookup" | "diagnostic" | "comparison" | "procedural"
    complexity: str  # "simple" | "complex"
    rewritten_queries: list[SubQuery]

    # retrieve 的輸出（每次 rewrite 時重置）
    documents: list[Document]

    # generate 的輸出
    generation: str

    # 流程控制
    retry_count: int       # rewrite_query 次數，上限 max_retries
    max_retries: int       # 預設 3，Graph 初始化時設定
    regenerate_count: int  # regenerate self-loop 次數，上限 max_regenerates
    max_regenerates: int   # 預設 2，防止無限重生成

    # 終止原因
    halt_reason: str

    # 認證（login_node 寫入）
    judgment_api_token: str

    # 多輪對話歷史
    messages: Annotated[list, add_messages]
```

### question vs messages

- `question`：本輪問題，從最新 HumanMessage 提取，進入 Graph 前設定
- `messages`：整個對話歷史，multi-turn
- `rewrite_query` 只修改 `rewritten_queries`，**不修改** `question`，
  讓 grader 始終能對比原始問題判斷答案品質

### documents 重置規則

每次 `retrieve` 執行時清空並重建 `documents`，
避免舊查詢的不相關文件污染後續 generate。

---

## Intent 分類

四類意圖，依問題特徵判斷：

| Intent | 典型問題 | 問題特徵 |
|---|---|---|
| `lookup` | 「民法第 184 條的內容？」「侵權行為的定義？」 | 查具體事實或定義 |
| `diagnostic` | 「被房東扣押金怎麼辦？」「老闆不付薪水？」 | 描述情境，要找解決方向 |
| `comparison` | 「民事和刑事責任的差異？」 | 比較兩個以上實體 |
| `procedural` | 「如何提起訴訟？」「申請法律扶助的步驟？」 | 問操作步驟或流程 |

### Complexity Override

```
出現「和」「還有」「以及」「同時」，或問了多個不同條文/法律
→ complexity = "complex"
→ 強制走子查詢分解，不管 intent 是什麼
```

---

## Retrieve 策略對照表

`analyze_query` 輸出的每個 `SubQuery.strategy` 對應以下搜尋方式：

| strategy | 觸發條件 | retrieve 做什麼 | 使用函式 |
|---|---|---|---|
| `law:semantic` | procedural / simple lookup（無條號）的 fallback | Chroma 語意搜尋 | `chunk_builder.search(query)` |
| `law:hyde` | lookup 無條號（概念型） | query 已是 HyDE 假設條文，直接 Chroma 搜尋 | `chunk_builder.search(query)` |
| `law:direct_lookup` | lookup 有具體法律名稱 + 條號 | Graph 直接查節點 | `law_graph.get_node(f"{pcode}#{article_no}")` |
| `law:graph_expand` | diagnostic | Chroma 搜尋 → 取出 article_no → Graph 遍歷引用鏈 | `chunk_builder.search()` + `law_graph.get_cited_with_edges()` |
| `judgment:tavily` | 問題提到判決/裁判/案例 | Tavily 搜尋 → 司法院 API 取全文 | placeholder |

### HyDE 在哪裡生成

HyDE 假設文件在 `analyze_query` 節點生成（LLM 呼叫），
存入 `SubQuery.query`。`retrieve` 節點看到 `law:hyde` 時
直接把 `query` 丟進 Chroma 搜尋，不再額外呼叫 LLM。

### 多個 SubQuery 時

依序搜尋每個 SubQuery，合併結果（去重後）存入 `documents`。
一個問題需要兩個來源時，`analyze_query` 負責拆成兩個 SubQuery
（各自帶不同 strategy），`retrieve` 只管執行，不做來源判斷。

### 舊版 tools 的去向

舊版 `tools/law.py` 的搜尋函式（`search_law_articles`、`get_related_articles` 等）
在新架構中直接被 `retrieve` 節點呼叫，不再透過 LangGraph tool 機制。

---

## Strategy Registry

`src/agent/strategy_registry.py` 是跨節點 strategy policy 的唯一來源。

### 新增 strategy 的流程

1. `StrategyName` Literal 加入新值
2. `STRATEGY_REGISTRY` 加入對應的 `StrategyConfig`
3. `retrieve.py` 加入 `if/elif` 分支（retrieval 實作）
4. `analyze_query.py` prompt 更新（告知 LLM 新 strategy）

### 目前 StrategyConfig 欄位

```python
class StrategyConfig(TypedDict):
    requires_grading: bool  # False = grade_documents 自動放行
```

**預留擴充欄位**（討論後再加）：
- `source: str` — `"law"` / `"judgment"`
- `fallback_strategy: str` — rewrite_query fallback
- `has_score: bool` — 結果是否附帶相似度分數

### retrieve 尚未遷入的原因

`retrieve.py` 各 strategy 的 retrieval 實作（if/elif 分支）
目前仍在 `retrieve.py`，未來可封裝進 `StrategyConfig` 的 `retriever` 欄位遷出。
現階段 strategy 僅 5 個，if/elif 可讀性足夠，暫不抽象。

---

## 路由邏輯

### grade_documents 之後

```
filtered_docs 非空                                → "generate"
filtered_docs 為空 且 retry_count < max_retries   → "rewrite_query"
filtered_docs 為空 且 retry_count >= max_retries  → "force_end"
```

**設計決策**：threshold 為 0（完全無相關文件才 rewrite），
不設最低篇數，結果不佳時再調整。

路由函式 `route_after_grade(state)` 實作在 `grade_documents.py`，
直接作為 LangGraph conditional edge 的 routing function 傳入。

**`law:direct_lookup` 跳過 grading**：使用者明確指定的條文不需判斷相關性。
`grade_documents.py` 查詢 `STRATEGY_REGISTRY["requires_grading"]`，
`False` 的 strategy 自動放行。
`retrieve` 在 Document metadata 帶入 `"strategy"` 欄位供此處使用。

**chunk grade vs graph grade**：不需區分。
`law:graph_expand` 產出的 Chroma 語意結果和引用展開結果
metadata strategy 相同，registry 都標記 `requires_grading=True`，一視同仁。
唯一例外是 `law:direct_lookup`（`requires_grading=False`）。

### generate 之後

```
幻覺 grader 通過 且 answer grader 通過             → "finish"
幻覺 grader 不通過                                → "regenerate"
answer grader 不通過 或 regenerate 達上限          → "rewrite_query"
```

> **⚠️ TBD：** 幻覺 grader 與 answer grader 是否拆成獨立節點待確認。

---

## 各節點職責

完整程式碼與 prompt 見 `references/nodes.md`。

| 節點 | 主要職責 | 讀 State | 寫 State |
|---|---|---|---|
| `login_node` | 取得司法院 API token（placeholder）| — | `judgment_api_token` |
| `analyze_query` | 分類 intent，生成 SubQuery 清單 | `question` | `intent`, `complexity`, `rewritten_queries` |
| `retrieve` | 依 strategy 搜尋，重置 documents | `rewritten_queries` | `documents` |
| `grade_documents` | LLM 逐篇相關性判斷，過濾不相關文件 | `question`, `documents` | `documents`（過濾後）|
| `generate` | 生成答案，執行 grader 路由 | `question`, `documents` | `generation` |
| `rewrite_query` | 改寫查詢，更新 retry_count | `question`, `generation` | `rewritten_queries`, `retry_count` |
| `force_end` | 達到上限，回傳查無結果說明 | `halt_reason` | `generation` |

---

## 程式碼位置規劃

```
src/agent/
  ├── state.py                # AgenticRAGState + SubQuery（strategy 型別引用 registry）
  ├── strategy_registry.py    # STRATEGY_REGISTRY + StrategyName + StrategyConfig
  ├── graph.py                # build_graph()，組裝所有節點與路由
  └── nodes/
      ├── __init__.py
      ├── analyze_query.py    # ✅ 完成
      ├── retrieve.py         # ✅ 完成
      ├── grade_documents.py  # ✅ 完成
      ├── generate.py         # ⚠️ TBD
      ├── rewrite_query.py    # ✅ 完成
      └── force_end.py        # ✅ 完成
```

> **注意：** 目前 `src/agent/` 仍為舊版架構（`login → agent ⇆ tool → END`），
> 待架構設計全部確認後統一重構。

---

## 與舊架構的關係

此 skill 取代 `law-agent-architecture` 中 `references/agent-layer.md`。
MCP Server、FastAPI 等外層包裝的設計規格仍見 `law-agent-architecture` skill。

---

## 架構修改流程

1. 確認影響哪個節點或 State 欄位
2. 更新此 SKILL.md 對應段落，移除或更新 TBD 標記
3. 更新 `references/nodes.md` 的節點實作
4. 再動程式碼
