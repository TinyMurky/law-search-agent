# FastAPI 層

## 這層做什麼

FastAPI 是**服務入口**，負責：
- 接收來自 MCP Server 的 HTTP 請求
- 把請求交給 LangGraph Agent 處理
- 把 Agent 的回答透過 SSE 串流回傳給呼叫者

FastAPI 不對外公開，只在 VPC 內部讓 MCP Server 存取。

```
MCP Server
    │  POST /search/stream
    ▼
FastAPI  ──── 呼叫 ────▶  LangGraph Agent
    │                          │
    │◀───── 串流回答 ───────────┘
    │
    │  SSE（逐 token 回傳）
    ▼
MCP Server
```

---

## 為什麼選 FastAPI

| 原因 | 說明 |
|---|---|
| 原生 async | Python async/await 支援，和 LangGraph 的非同步執行相容 |
| SSE 簡單 | 搭配 `sse-starlette` 可以很容易實作串流回應 |
| 型別驗證 | 搭配 Pydantic 自動驗證請求格式 |

---

## 介面合約

### Endpoints

| Method | Path | 說明 | 回應格式 |
|---|---|---|---|
| `POST` | `/search` | 等待完整回答再回傳 | JSON |
| `POST` | `/search/stream` | 逐 token 串流回答 | SSE |
| `GET` | `/health` | 健康檢查 | JSON |

### Request 格式

```json
{
  "query": "消費者保護相關的法條有哪些？"
}
```

### Response 格式

**`/search`（完整回答）：**
```json
{
  "answer": "根據消費者保護法第...",
  "sources": [
    {"law_name": "消費者保護法", "article_no": "第 1 條"}
  ]
}
```

**`/search/stream`（SSE 串流）：**
```
data: 根據

data: 消費者保護法

data: 第七條規定...

data: [DONE]
```

每行是一個小片段（token），客戶端逐行接收，拼起來就是完整回答。

---

## 關鍵模式

### SSE 串流

簡單說：SSE（Server-Sent Events）就像廣播電台，
伺服器說一個字就馬上發出去，不等到整篇文章說完才傳給你。

```python
# 簡化示意，非完整程式碼
from sse_starlette.sse import EventSourceResponse

@app.post("/search/stream")
async def search_stream(request: SearchRequest):
    async def token_generator():
        # Agent 每產生一個字，就立刻 yield 出去
        async for event in agent.astream_events({"messages": [request.query]}):
            if event["event"] == "on_chat_model_stream":
                token = event["data"]["chunk"].content
                yield {"data": token}
        yield {"data": "[DONE]"}   # 告訴客戶端已結束

    return EventSourceResponse(token_generator())
```

### 與 Agent 的呼叫方式

FastAPI 直接 import 並呼叫 LangGraph graph，不透過 HTTP：

```python
# 非完整程式碼，示意資料流
from agent.graph import law_graph   # 直接 import graph

result = await law_graph.ainvoke({"messages": [query]})    # 等待完整結果
# 或
events = law_graph.astream_events({"messages": [query]})   # 串流
```

---

## 環境變數

| 變數 | 說明 |
|---|---|
| `GEMINI_API_KEY` | LangGraph Agent 使用的 Gemini API Key |
| `JUDGMENT_API_USERNAME` | 司法院 API 帳號 |
| `JUDGMENT_API_PASSWORD` | 司法院 API 密碼 |

---

## 啟動方式

```bash
uvicorn src.cmd.api_server.main:app --host 0.0.0.0 --port 8000
```

---

## Phase 變化

Phase 1 → Phase 2：**此層不需要修改。**
DB 升級在 Agent 的 tool 內處理，FastAPI 的 endpoint 和串流邏輯不變。
