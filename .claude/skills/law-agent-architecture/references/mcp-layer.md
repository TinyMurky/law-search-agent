# MCP Server 層

## 這層做什麼

MCP Server 是**協議轉換層**，唯一的工作是：
把 Claude 客戶端（Claude Desktop、Claude Code）發來的 MCP 請求，
翻譯成 FastAPI 的 HTTP call，再把 FastAPI 回傳的串流轉回去給客戶端。

自己不包含任何法律搜尋邏輯，邏輯全在 FastAPI + Agent 那側。

```
Claude 客戶端
    │  ask_law_agent("消費者保護相關法條")
    │  MCP Streamable-HTTP
    ▼
MCP Server
    │  POST /search/stream  {"query": "消費者保護相關法條"}
    │  HTTP SSE
    ▼
FastAPI
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
| `ask_law_agent` | `query: str`（自然語言問題） | 串流文字 | 把問題交給 Agent，串流回答 |

目前只有一個 tool，因為完整的搜尋策略由 Agent 決定，
不需要在客戶端這側拆成多個 tool。

### 對下：呼叫 FastAPI 的方式

```
POST http://api:8000/search/stream
Content-Type: application/json

{"query": "使用者的問題"}
```

回應是 SSE 格式，每行是一個 token（文字片段），MCP Server 逐行轉發給客戶端。

---

## 關鍵模式

### 串流代理（Streaming Proxy）

簡單說：MCP Server 就像一個「翻譯+轉播員」，
FastAPI 說一個字，MCP Server 馬上轉給客戶端一個字，不等到全部說完才回傳。

```python
# 簡化示意，非完整程式碼
@mcp.tool()
async def ask_law_agent(query: str):
    """搜尋法條與判決書。"""
    # 開始跟 FastAPI 建立串流連線
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", f"{API_URL}/search/stream",
                                  json={"query": query}) as response:
            # FastAPI 每吐出一行，馬上轉發給客戶端
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    yield line[6:]   # 去掉 "data: " 前綴，只回傳內容
```

### 啟動方式

```python
# src/cmd/mcp_server/main.py
mcp = FastMCP("law-search-agent", transport="streamable-http", port=8001)

if __name__ == "__main__":
    mcp.run()
```

---

## 環境變數

| 變數 | 說明 | 預設值 |
|---|---|---|
| `API_BASE_URL` | FastAPI 的位址 | `http://localhost:8000` |

---

## Phase 變化

Phase 1 → Phase 2：**此層不需要修改。**
DB 的升級發生在 Agent 層，MCP Server 完全感知不到。
