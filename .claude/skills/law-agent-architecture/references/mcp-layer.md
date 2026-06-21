# MCP Server 層

## 這層做什麼

MCP Server 是**協議轉換層**，唯一的工作是：
把 Claude 客戶端（Claude Desktop、Claude Code）發來的 MCP 請求，
轉成對 LangGraph Agent 的直接呼叫（`import` 同一個 `law_graph`，
不經過 FastAPI），等 Agent 跑完整個 graph、組成完整答案後再回傳
給客戶端（**不是逐字轉發**，原因見下方〈為什麼 MCP 這層做不到
真串流〉）。

自己不包含任何法律搜尋邏輯，邏輯全在 Agent 那側。MCP Server 跟
FastAPI 是兩個平行的 interface，各自直接呼叫 Agent，互相不知道
對方存在（細節見 `SKILL.md` 的〈為什麼是平行而不是鏈接〉）。

```
Claude 客戶端
    │  ask_law_agent("消費者保護相關法條")
    │  MCP Streamable-HTTP
    ▼
MCP Server
    │  await law_graph.ainvoke({"messages": [query]})
    │  Python function call（同一個 process 內直接呼叫）
    ▼
LangGraph Agent
```

---

## 為什麼選 Streamable-HTTP

MCP 支援兩種傳輸方式：

| 方式 | 說明 | 適合場合 |
|---|---|---|
| `stdio` | 本機行程直接通訊 | 開發測試、單機使用 |
| `Streamable-HTTP` | 走 HTTP，支援遠端部署 | 生產環境、容器部署 |

選 Streamable-HTTP 的原因：未來要部署到 AWS ECS，需要透過網路連線，
stdio 只能在同一台機器上使用。

---

## 介面合約

### 暴露給 Claude 客戶端的 MCP Tools

| Tool 名稱 | 輸入 | 輸出 | 說明 |
|---|---|---|---|
| `ask_law_agent` | `query: str`（自然語言問題） | 完整文字 | 把問題交給 Agent，回傳完整回答（可選附進度通知，見下） |

目前只有一個 tool，因為完整的搜尋策略由 Agent 決定，
不需要在客戶端這側拆成多個 tool。

### 對下：呼叫 Agent 的方式

MCP Server 直接 `import` 並呼叫 LangGraph graph，跟 FastAPI 那層
完全一樣的呼叫方式（不透過 HTTP）：

```python
# 非完整程式碼，示意資料流
from agent.graph import law_graph

result = await law_graph.ainvoke({"messages": [query]})
answer: str = result["generation"]
```

---

## 為什麼 MCP 這層做不到真串流

MCP 的 tool call 在協議上是**一次性 request/response**：tool 函式
必須回傳一個完整、可序列化的結果，不能像 FastAPI 那層一樣用
`yield` 把片段內容當作最終結果陸續吐出去——這樣寫在 FastMCP 會
直接丟 `'async_generator' object is not iterable`。也就是說，
即使 Agent 本身有 `astream_events` 可以逐 token 吐出，從 MCP
Server 到 Claude 客戶端這段，protocol 本身就不支援逐字轉發，
所以 MCP Server 選擇直接呼叫 `ainvoke`（等完整結果），而不是
`astream_events`（FastAPI 那層才用得到串流的好處）。

如果要在等待期間給使用者一點回饋，可以用 MCP 內建的進度通知
`ctx.report_progress(...)`（需走 Streamable-HTTP transport），
但這個訊息會不會被 host（Claude Desktop / Claude Code）渲染成
聊天視窗裡看得到的文字，取決於 host 的實作，多數只會顯示成
進度條或百分比，不保證等同「逐字跳出」的體感。**這個限制是
MCP 規格本身的設計，不是這個專案能繞過的**，如果展示重點是
「讓使用者看到逐字輸出」，應該直接接 FastAPI 的 `/search/stream`
（例如用 Streamlit demo），不要透過 MCP 這層。

---

## 關鍵模式

### 直接呼叫 Agent（Direct Call）

MCP Server 跟 FastAPI 共用同一個 `law_graph`（在啟動時各自建立
一份依賴，跟現在 `chat/main.py` 的 `_load_deps` 模式一樣），
拿到完整結果後直接回傳，不用累積 SSE 片段（因為根本沒有經過
FastAPI 的 SSE endpoint）：

```python
# 簡化示意，非完整程式碼
from agent.graph import law_graph

@mcp.tool()
async def ask_law_agent(query: str) -> str:
    """搜尋法條與判決書。"""
    result = await law_graph.ainvoke({"messages": [query]})
    return result["generation"]
```

若想在等待期間給使用者一點進度回饋（不保證每個 host 都會顯示
成可見文字），可以額外帶 `ctx: Context` 參數，搭配
`law_graph.astream_events(...)` 在迴圈裡呼叫
`await ctx.report_progress(progress=..., message=token)`，
最後仍是回傳累積後的完整字串（tool 的回傳值本身不能是串流）。

### 啟動方式

```python
# src/entrypoints/mcp_server/main.py
mcp = FastMCP("law-search-agent", transport="streamable-http", port=8001)

if __name__ == "__main__":
    mcp.run()
```

---

## 環境變數

MCP Server 自己 import Agent，所以需要的環境變數跟 Agent 本身一樣
（不再需要 `API_BASE_URL`，因為不經過 FastAPI）：

| 變數 | 說明 |
|---|---|
| `GEMINI_API_KEY` | LangGraph Agent 使用的 Gemini API Key |
| `JUDGMENT_API_USERNAME` | 司法院 API 帳號 |
| `JUDGMENT_API_PASSWORD` | 司法院 API 密碼 |

---

## Phase 變化

Phase 1 → Phase 2：**此層不需要修改。**
DB 的升級發生在 Agent 層，MCP Server 完全感知不到。
