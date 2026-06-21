# FastAPI 層

## 這層做什麼

FastAPI 是**服務入口**，負責：
- 接收來自網頁前端 / Streamlit demo 的 HTTP 請求
- 把請求交給 LangGraph Agent 處理
- 把 Agent 的回答透過 SSE 串流回傳給呼叫者

FastAPI 跟 MCP Server 是兩個平行的對外 interface，各自直接呼叫
同一個 Agent，互不轉發（細節見 `SKILL.md` 的〈為什麼是平行而不是
鏈接〉）。是否對外公開視部署環境決定——本機demo 或內網測試可以
直接開放，正式環境再視需求加 CORS／認證。

```
網頁前端 / Streamlit
    │  POST /search/stream
    ▼
FastAPI  ──── 呼叫 ────▶  LangGraph Agent
    │                          │
    │◀───── 串流回答 ───────────┘
    │
    │  SSE（逐 token 回傳）
    ▼
網頁前端 / Streamlit
```

---

## 為什麼選 FastAPI

| 原因 | 說明 |
|---|---|
| 原生 async | Python async/await 支援，和 LangGraph 的非同步執行相容 |
| SSE 內建 | FastAPI 內建 `fastapi.sse` 模組（`EventSourceResponse` / `ServerSentEvent`），不需要額外裝 `sse-starlette`，且內建處理了 SSE 最佳實踐（定時 `ping` 防 proxy 斷線、`Cache-Control: no-cache`、`X-Accel-Buffering: no`）|
| 型別驗證 | 搭配 Pydantic 自動驗證請求格式 |

> 實作這部分前，先讀 FastAPI 官方文件
> [Server-Sent Events (SSE)](https://fastapi.tiangolo.com/tutorial/server-sent-events/#serversentevent)，
> 了解 `EventSourceResponse` 與 `ServerSentEvent` 的完整用法（包含
> `Last-Event-ID` 斷線重連），不要只憑這份摘要動手寫。

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

用 FastAPI 內建的 `fastapi.sse`（不是第三方 `sse-starlette`）：
把 `response_class` 設成 `EventSourceResponse`，path operation
函式直接 `yield ServerSentEvent`，FastAPI 負責把它編碼成
`data: ...\n\n` 格式並處理連線細節。實作前務必先讀
[FastAPI 官方 SSE 文件](https://fastapi.tiangolo.com/tutorial/server-sent-events/#serversentevent)，
下面只是示意，不是完整寫法。

```python
# 簡化示意，非完整程式碼
from typing import AsyncIterable
from fastapi.sse import EventSourceResponse, ServerSentEvent

@app.post("/search/stream", response_class=EventSourceResponse)
async def search_stream(
    request: SearchRequest,
) -> AsyncIterable[ServerSentEvent]:
    # Agent 每產生一個字，就立刻 yield 出去
    async for event in agent.astream_events({"messages": [request.query]}):
        if event["event"] == "on_chat_model_stream":
            token = event["data"]["chunk"].content
            yield ServerSentEvent(data=token)
    yield ServerSentEvent(data="[DONE]")   # 告訴客戶端已結束
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
