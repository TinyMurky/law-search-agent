# LangGraph Agent 層

## 這層做什麼

Agent 層是**決策核心**，負責：
- 理解使用者的問題
- 決定要呼叫哪些工具、按什麼順序
- 把多個工具的結果整合成一個回答

簡單說：Agent 就像一個法律助手，收到問題後會思考「我要查哪部法、
要不要看引用關係、要不要查判決書」，然後一步一步去查，最後整理成答案。

```
FastAPI 傳入問題
       │
       ▼
  login_node（第一次啟動，取得司法院 token）
       │
       ▼
  agent_node（Gemini 決定：要查什麼？）
       │
   有需要查  ──────────────▶  tool_node（執行工具）
       │                           │
       │◀──────── 查到結果 ─────────┘
       │
   回答夠了 ──▶ END（回傳最終答案）
```

---

## 為什麼選 LangGraph

| 原因 | 說明 |
|---|---|
| 可以循環 | 查完一個工具後，AI 可以再決定查另一個，直到答案夠完整 |
| State 管理 | 對話歷史、token 等資料統一放在 State，不用手動傳來傳去 |
| 容易加工具 | 新增法律工具只要定義 function + 加進 tools list |
| LangChain 整合 | 與 Chroma、Gemini 的整合都有現成支援 |

---

## State 設計

State 就像一個「對話紀錄本」，在整個 Agent 執行過程中傳遞。
每個 node 從 State 讀取需要的資訊，處理完再把結果寫回 State。

```python
class LawSearchingState(TypedDict):
    messages: list[BaseMessage]
    # 存放整個對話歷史，包含使用者的問題、Agent 的回答、工具的查詢結果
    # 每次有新訊息都會自動附加（不會覆蓋）

    judgment_api_token: str
    # 司法院 API 的登入 token
    # 由 login_node 在啟動時寫入，之後所有判決書工具都從這裡取用
    # 這樣不用每次查判決書都重新登入
```

---

## Graph 流程

### login_node

- 只在 Graph 第一次啟動時執行
- 讀取 `.env` 的帳密，向司法院 API 取得 token
- 把 token 寫入 `State.judgment_api_token`
- 登入失敗就中止，避免後續查判決書時才爆錯

### agent_node

- 由 Gemini 決定：要回答使用者，還是要先呼叫工具查資料？
- 如果決定呼叫工具，會在訊息中指定要呼叫哪個 tool、傳什麼參數

### tool_node

- LangGraph 內建，自動執行 agent_node 指定的工具
- 把工具回傳的結果加進 `State.messages`，讓 agent_node 看到

### 路由邏輯

```
agent_node 輸出後：
  - 有 tool_calls（要查東西）→ 去 tool_node
  - 沒有 tool_calls（答案夠了）→ END
```

---

## 介面合約

### Tools 清單（Phase 1）

#### 法條工具

| Tool | 輸入 | 說明 |
|---|---|---|
| `search_law_articles(query)` | 自然語言 | Chroma 語義搜尋，找相關條文 |
| `get_related_articles(pcode, article_no)` | 條文編號 | NetworkX 圖遍歷，找引用/被引用條文 |
| `get_law_articles(pcode, chapter?)` | pcode | 取得某法律的完整條文 |

#### 判決書工具

| Tool | 輸入 | 說明 |
|---|---|---|
| `search_judgments(query)` | 自然語言 | Tavily 搜尋司法院網站，找判決書 ID |
| `get_judgment(judgment_id)` | 判決書 ID | 用 State 的 token 呼叫司法院 API 取全文 |

> **pcode**：每部法律的唯一代號，例如民法是 `B0000001`

### 輸入（從 FastAPI 接收）

```python
{"messages": ["消費者保護相關的法條有哪些？"]}
```

### 輸出（回傳給 FastAPI）

```python
{"messages": [..., AIMessage(content="根據消費者保護法第七條...")]}
```

---

## 關鍵模式

### Async Tool（非同步工具）

所有 tool 都要寫成 async，因為部分工具需要呼叫外部 API（司法院），
同步寫法會卡住整個 server。

```python
# 簡化示意
@tool
async def get_judgment(judgment_id: str) -> str:
    """取得判決書全文。"""
    # 從 State 取 token → 呼叫司法院 API → 回傳全文
    ...
```

### 程式碼位置

```
src/agent/
  ├── state.py     # LawSearchingState 定義
  ├── graph.py     # Graph 結構（login → agent ⇆ tool → END）
  └── tools/
      ├── law.py       # 法條相關工具
      └── judgment.py  # 判決書相關工具
```

---

## Phase 變化

Phase 1 → Phase 2：**只需修改 Tools，Graph 結構不變。**

| 變動項目 | Phase 1 | Phase 2 |
|---|---|---|
| `search_law_articles` 底層 | Chroma | Neo4j 向量搜尋 |
| `get_related_articles` 底層 | NetworkX | Neo4j 圖查詢（Cypher） |
| State、Graph 結構 | 不變 | 不變 |
| login_node、agent_node | 不變 | 不變 |
