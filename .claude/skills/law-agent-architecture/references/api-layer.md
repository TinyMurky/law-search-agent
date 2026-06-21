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

### 模組結構：create_app(agent) 工廠函式，不是 class、不是模組級單例

FastAPI 的程式碼分成兩個檔案，職責切開：

```
src/api/app.py              ← 純邏輯：create_app(agent) -> FastAPI
src/agent/bootstrap.py      ← 共用：build_agent_from_env() -> CompiledStateGraph
src/cmd/api_server/main.py  ← 薄的進入點：把上面兩個接起來、跑 uvicorn
```

`src/api/app.py` 不碰 `.env`、不知道 Agent 怎麼建出來的，agent 是
呼叫 `create_app()` 時當參數傳入（注入），不是在裡面 import 一個
全域 `law_graph` 變數：

```python
# src/api/app.py（簡化示意，非完整程式碼）
from fastapi import FastAPI
from langgraph.graph.state import CompiledStateGraph


def create_app(agent: CompiledStateGraph) -> FastAPI:
    """組裝 FastAPI app，把 Agent 當依賴注入進來。"""
    app = FastAPI()

    @app.post("/search")
    async def search(req: SearchRequest) -> SearchResponse:
        result = await agent.ainvoke({"messages": [req.query]})
        return SearchResponse(answer=result["generation"])

    return app
```

```python
# src/cmd/api_server/main.py（簡化示意，非完整程式碼）
import uvicorn

from agent.bootstrap import build_agent_from_env
from api.app import create_app
from logging_config import setup_logging


def main() -> None:
    setup_logging()
    agent = build_agent_from_env()
    app = create_app(agent)
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()
```

**為什麼是工廠函式，不是 class**：`FastAPI()` 物件本身已經是
framework 提供的容器（路由、`app.state` 都有了），再包一層
`class LawSearchAPI: def __init__(self, agent): self.app = FastAPI()`
不會多換到任何行為，純粹多一層轉發。這個專案的慣例是：class
只用在真的有內部狀態與邏輯要管理的東西（`src/ingestion/` 的
`ChunkBuilder`、`NxLawGraph` 等），組裝/orchestration 層（`build_graph(...)`
也是同樣風格）一律用函式。

**為什麼是工廠函式，不是模組級 `app = FastAPI()` 單例**：工廠函式
每次呼叫都回傳全新的 app 物件，測試時 `create_app(fake_agent)`
天然互不干擾；模組級單例需要靠 `app.state.agent = ...` 改全域
可變狀態，平行跑測試（例如 `pytest-xdist`）時要額外小心互相
汙染。換到的唯一好處（`uvicorn api.app:app --reload` 可以單獨啟動
熱重載）目前用不到，所以不選這個方案。

### build_agent_from_env()：三個 entry point 共用，不要各自複製

`chat`、`api_server`、未來的 `mcp_server` 都需要同一套「讀
`.env` → 建 `ChunkBuilder`/`NxLawGraph`/LLM → `build_graph(...)`」
流程，這套邏輯收斂在 `src/agent/bootstrap.py` 的
`build_agent_from_env() -> CompiledStateGraph`，三邊都呼叫它，
不要各自複製一份（複製多份意味著未來改依賴注入方式要同步改
三處）。

---

## 環境變數

| 變數 | 說明 |
|---|---|
| `GEMINI_API_KEY` | LangGraph Agent 使用的 Gemini API Key |
| `JUDGMENT_API_USERNAME` | 司法院 API 帳號 |
| `JUDGMENT_API_PASSWORD` | 司法院 API 密碼 |

---

## 啟動方式

`main()` 內部呼叫 `uvicorn.run(app, ...)`（programmatic，不是
`uvicorn module:app` 的 CLI 字串形式），跟其他 `src/cmd/*/main.py`
一樣用 `uv run` 直接執行整個腳本：

```bash
make api-server
# 等同於：PYTHONPATH=src uv run src/cmd/api_server/main.py
```

### Streamlit demo 怎麼呼叫這個 API

`src/cmd/streamlit_demo/main.py` 是另一個獨立 process（`streamlit
run` 啟動，不是 `uvicorn`），內部單純用 `httpx` 打
`/search/stream`，跟未來真正的網頁前端是同一種角色——它**不會**
import Agent，所以不適用 `create_app(agent)` 那套注入設計，純粹
是 FastAPI 的其中一個呼叫者：

```python
# src/cmd/streamlit_demo/main.py（簡化示意，非完整程式碼）
import httpx
import streamlit as st

_API_URL = "http://localhost:8000/search/stream"


def _stream_answer(query: str):
    with httpx.Client() as client:
        with client.stream("POST", _API_URL, json={"query": query}) as r:
            for line in r.iter_lines():
                if line.startswith("data: ") and line != "data: [DONE]":
                    yield line[6:]


query = st.text_input("問題")
if query:
    st.write_stream(_stream_answer(query))
```

因為是純展示用途，這個檔案不拆 module、不寫單元測試，跟其他
`src/cmd/*/main.py` 進入點的慣例一致。FastAPI 跟 Streamlit 是兩個
獨立 process，要分別啟動（兩個 terminal）：

```makefile
.PHONY: api-server
api-server: ## 啟動 FastAPI server（streamlit-demo 需要先啟動這個，留在前景跑）
	@PYTHONPATH=src uv run src/cmd/api_server/main.py

.PHONY: streamlit-demo
streamlit-demo: ## 啟動 Streamlit demo（需先在另一個 terminal 跑 make api-server）
	@PYTHONPATH=src uv run streamlit run src/cmd/streamlit_demo/main.py
```

沒有做成一鍵同時啟動兩個 process，因為要正確處理「確認 FastAPI
就緒才啟動 Streamlit」「Ctrl+C 連帶關閉背景 process」這些問題，
對 demo 用途來說不值得在 Makefile 裡硬塞程序管理邏輯；真的需要
一鍵啟動時，再考慮 `docker-compose` 或簡單的 shell script。

---

## Phase 變化

Phase 1 → Phase 2：**此層不需要修改。**
DB 升級在 Agent 的 tool 內處理，FastAPI 的 endpoint 和串流邏輯不變。
