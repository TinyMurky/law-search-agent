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

```
Claude Desktop / Claude Code（使用者端）
         │
         │  MCP Streamable-HTTP (:8001)
         ▼
 ┌───────────────────┐
 │   MCP Server      │  協議轉換層：把 MCP 請求翻譯成 HTTP call
 └────────┬──────────┘
          │  HTTP SSE（內部 VPC）
          ▼
 ┌───────────────────┐
 │   FastAPI         │  服務入口：管理請求、回應、串流
 └────────┬──────────┘
          │  Python function call
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

---

## 層級總覽

| 層級 | 職責 | 程式碼位置 | 實作狀態 |
|---|---|---|---|
| **MCP Server** | 把 MCP 協議轉成 FastAPI HTTP call | `src/cmd/mcp_server/` | 未實作 |
| **FastAPI** | 對外 API、SSE 串流、呼叫 Agent | `src/cmd/api_server/` | 未實作 |
| **LangGraph Agent** | 決策、工具選擇、對話管理 | `src/agent/` | 未實作 |
| **DB Layer** | 向量搜尋 + 圖遍歷 | `src/ingestion/` | Phase 1 完成 |

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
| `references/mcp-layer.md` | MCP Server：工具定義、串流代理、Streamable-HTTP 設定 |
| `references/api-layer.md` | FastAPI：endpoint 列表、SSE 串流寫法、與 Agent 的呼叫方式 |
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
