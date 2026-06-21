---
name: law-agent-architecture
description: >
  法律搜尋 Agent 的完整系統架構文件。記錄 MCP Server、FastAPI、
  LangGraph Agent、Vector DB / Graph DB 四層的設計決策、對外介面
  與關鍵模式，並按 Phase 區分現況與規劃。
  當使用者詢問「這個系統怎麼運作」、「各層之間怎麼溝通」、
  「某功能應該放在哪一層」、「Phase 1 和 Phase 2 有什麼差異」，
  或 AI agent 動手寫程式前想確認整體架構時，必須參照此 skill。
  架構有任何變更，應先更新此 skill 再動程式碼。
---

# 法律搜尋 Agent 系統架構

## 系統全貌

MCP Server 與 FastAPI 是**兩個平行的對外介面**，各自直接呼叫同一個
LangGraph Agent，不是「MCP 轉發給 FastAPI 再轉發給 Agent」的鏈接
關係——見下方〈為什麼是平行而不是鏈接〉。

```
Claude Desktop / Claude Code        Streamlit / 網頁前端
         │                                  │
         │ MCP Streamable-HTTP (:8001)      │ HTTP / SSE (:8000)
         ▼                                  ▼
 ┌────────────────┐               ┌────────────────────┐
 │   MCP Server   │               │      FastAPI        │
 │ 工具呼叫介面    │               │  服務入口/SSE 串流   │
 └────────┬───────┘               └─────────┬───────────┘
          │                                 │
          │   Python function call（各自直接呼叫，不互相轉發）
          └────────────────┬────────────────┘
                            ▼
                 ┌───────────────────┐
                 │  LangGraph Agent  │  決策核心：決定要查什麼、怎麼查
                 └──────┬─────┬──────┘
                        │     │
                        ▼     ▼
                   Chroma   NetworkX      ← Phase 1
                  (向量搜尋) (圖遍歷)
                        │     │
                        └──┬──┘
                  (Phase 2 統一換成 Neo4j)
```

### 為什麼是平行而不是鏈接

一開始的規劃是 MCP Server 收到請求後轉發給 FastAPI（HTTP call），
但實測後發現這個鏈接對 MCP 這條路徑沒有任何好處：MCP tool call
在協議上是一次性 request/response，沒辦法把 FastAPI 的 SSE 串流
逐字轉發給 Claude 客戶端，只能整批收完再回傳——也就是說，不管
MCP Server 是去 HTTP 打 FastAPI 再累積，還是直接呼叫
`law_graph.ainvoke(...)` 拿一個完整結果，對 Claude 客戶端而言
結果完全一樣，多繞一層 HTTP 純粹是 overhead。

因此兩個 interface 改成各自直接 `import` 並呼叫
`src/agent/graph.py` 的 LangGraph Agent：
- **FastAPI** 面向 Streamlit demo / 未來網頁前端，保留真正的逐 token
  SSE 串流（`astream_events`）。
- **MCP Server** 面向 Claude 客戶端，回傳完整結果（`ainvoke`），
  可選搭配 `ctx.report_progress(...)` 給進度通知（不保證每個 host
  都顯示成可見文字）。

如果未來 MCP Server 與 FastAPI 真的需要拆成兩個獨立部署、獨立
scale 的 service（例如其中一個對外網開放，另一個只留內網），
中間補一層 HTTP 是合理的部署選擇，但那是**部署拓樸**的考量，
不是協議相容性的要求——目前先以「同一個部署單位，兩個平行
interface」設計。

### 共用的 Agent 建立邏輯：build_agent_from_env()

`chat`、`api_server`、未來的 `mcp_server` 三個 entry point 都需要
「載入 `.env`、建立 `ChunkBuilder`/`NxLawGraph`/LLM、組裝
`build_graph(...)`」這一整套流程——目前 `src/entrypoints/chat/main.py` 的
`_load_deps()` 就是這套邏輯，但只活在 `chat` 自己的檔案裡。

決定抽成 `src/agent/bootstrap.py` 的共用函式
`build_agent_from_env() -> CompiledStateGraph`，三個 entry point
都改成呼叫它，不再各自複製一份。原因：這套邏輯不是「每個 entry
point 各自的事」，而是「怎麼從環境變數生出一個可用的 Agent」這
件事本身只有一種正確答案，重複三份只會在未來改依賴注入方式時
要同步改三處。

### Streamlit demo：FastAPI 的其中一個呼叫者，不是新的一層

`src/entrypoints/streamlit_demo/main.py` 是純粹的 demo 用途，內部用
`httpx` 呼叫 FastAPI 的 `/search/stream`（跟網頁前端是同一種角色），
**不會** import 或建立 Agent，所以不適用「平行 interface 各自注入
Agent」那套設計。它單檔案實作，不拆 module、不寫單元測試，跟
`src/entrypoints/*/main.py` 其他進入點的慣例一致（這些薄的 wiring 腳本
本來就不在 `tests/` 的覆蓋範圍內，邏輯都收斂在 `src/agent/`、
`src/ingestion/` 才測）。細節見 `references/api-layer.md`。

---

## 層級總覽

| 層級 | 職責 | 程式碼位置 | 實作狀態 |
|---|---|---|---|
| **MCP Server** | 把 MCP tool call 轉成對 Agent 的直接呼叫，回傳完整結果 | `src/entrypoints/mcp_server/` | 未實作 |
| **FastAPI** | 對外 API、SSE 串流、直接呼叫 Agent | `src/api/`（app 邏輯）+ `src/entrypoints/api_server/`（entry point） | 未實作 |
| **LangGraph Agent** | 決策、工具選擇、對話管理（被 MCP Server 與 FastAPI 兩個 interface 共用） | `src/agent/`（含共用的 `bootstrap.py`） | 未實作 |
| **DB Layer** | 向量搜尋 + 圖遍歷 | `src/ingestion/` | Phase 1 完成 |
| **Streamlit Demo**（非核心層，純展示用） | 純 HTTP 呼叫 FastAPI 的 `/search/stream`，不碰 Agent | `src/entrypoints/streamlit_demo/` | 未實作 |

---

## Phase 對照表

| 層級 | Phase 1（目前規劃） | Phase 2（未來） |
|---|---|---|
| MCP Server | FastMCP + Streamable-HTTP | 同左，不變 |
| FastAPI | uvicorn + SSE | 同左，不變 |
| Agent | LangGraph + Gemini | 同左，不變 |
| Vector DB | Chroma（本機） | Neo4j 內建向量索引 |
| Graph DB | NetworkX（記憶體） | Neo4j（取代 NetworkX） |

Phase 2 的核心變化：Chroma + NetworkX 兩套系統統一換成一套 Neo4j，
其他三層程式碼幾乎不需要改動。

---

## 各層詳細規格

每層的設計決策、介面合約、關鍵模式分別記錄在：

| Reference 檔案 | 說明 |
|---|---|
| `references/mcp-layer.md` | MCP Server：工具定義、直接呼叫 Agent 的方式、Streamable-HTTP 設定 |
| `references/api-layer.md` | FastAPI：endpoint 列表、SSE 串流寫法、與 Agent 的呼叫方式、`create_app(agent)` 工廠模式、Streamlit demo 怎麼呼叫它 |
| `references/agent-layer.md` | **已過時，請改看 `law-rag-agent` skill**（State、Graph 流程、節點、Strategy Registry 的現行設計都在那裡）|
| `references/db-layer.md` | DB Layer：Chroma + NetworkX（Phase 1）→ Neo4j（Phase 2） |

---

## 架構修改流程

修改架構時，先更新 skill 再動程式碼，確保文件和程式碼保持一致。

**步驟：**
1. 確認影響哪一層（查上方層級總覽表）
2. 開啟對應的 `references/*.md` 更新內容
   - 技術選型有變 → 更新「為什麼選這個技術」段落
   - 介面有變（新增/移除 endpoint 或 tool）→ 更新「介面合約」段落
   - 實作模式有變 → 更新「關鍵模式」段落
3. 若涉及 Phase 升級 → 同步更新上方 Phase 對照表
4. 確認修改後，再動程式碼

**新增一層：**
在層級總覽表加一行，在 `references/` 新增對應的 `<layer>.md`，
參照現有 reference 檔案的段落結構。
