# 程式碼風格規範

## 工具

| 工具 | 說明 |
|---|---|
| **pycodestyle** | PEP 8 格式檢查，包含縮排、空白、行長等 |
| **mccabe** | 圈複雜度（Cyclomatic Complexity）檢查 |
| **mypy** | 靜態型別檢查，搭配 pydantic plugin |

## 規則

- 每行不超過 **80 字元**（pycodestyle E501）
- mccabe 複雜度上限：**10**
  - 複雜度 = 函式內的分支路徑數（if / for / while / except 各算一條）
  - 超過 10 代表函式邏輯太複雜，需要拆分成更小的函式
- 所有函式必須有 **return type annotation**（mypy `disallow_untyped_defs`）
- 避免回傳 `Any`（mypy `warn_return_any`）

## mypy 特殊情況

`@computed_field` + `@property` 的堆疊是 pydantic/mypy 的已知限制，
需加 `# type: ignore[prop-decorator]`：

```python
@computed_field  # type: ignore[prop-decorator]
@property
def pcode(self) -> str:
    ...
```

## 執行方式

```bash
make lint        # pycodestyle + mccabe
make type-check  # mypy
make test        # pytest
```

---

# 專案目標

law-searching-agent 目標為協助使用者搜索法律條文與判決書, 有條理的呈現給使用者。

# 相關 API 文件

- [全國法規資料庫 Open API](https://law.moj.gov.tw/api/swagger/index.html#/Ch/Ch_Law)
- [判決書 API文件](./docs/裁判書開放API規格說明(1140822版).pdf)

# Tech Stack

## 完整 Stack 總覽

| 層級 | 工具 | 說明 |
|---|---|---|
| **LLM** | Gemini API | `langchain-google-genai` |
| **Embedding** | gemini-embedding-001 | Google 官方 embedding，與 Gemini 同生態系 |
| **Agent Framework** | LangGraph + LangChain | agent 主框架 |
| **向量搜尋（第一階段）** | Chroma | 本地語義搜尋 |
| **圖遍歷（第一階段）** | NetworkX | in-memory 圖結構 |
| **向量搜尋 + 圖（第二階段）** | Neo4j | 統一處理向量與圖，適合生產環境 |
| **資料處理** | zipfile + json + regex + tqdm | 解析法條 ZIP，抽取引用關係 |
| **API Server** | FastAPI | 對外提供服務，async 相容 LangGraph |
| **套件管理** | uv | 快速的現代 Python 套件管理 |

---

## LLM 與 Embedding

使用 Gemini API，LLM 與 Embedding 共用同一生態系：

```python
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings

llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash")
embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
```

---

## API Server

FastAPI 對外暴露服務，async 原生支援，與 LangGraph 的 async 執行相容：

```python
from fastapi import FastAPI
from langgraph.graph import StateGraph

app = FastAPI()

@app.post("/search")
async def search_law(query: str):
    result = await graph.ainvoke({"messages": [query]})
    return result
```

---

## 資料儲存架構

法條資料有兩種查詢需求，需要兩種不同的儲存方式：

1. **語義查詢**：「有什麼法條保護消費者隱私？」— 使用者不知道法律名稱，找概念
2. **結構查詢**：「民法第184條引用了哪些條文？」— 沿著條文間的引用關係導航

因此採用 **向量資料庫 + 圖資料庫** 的混合架構。

---

## 向量資料庫：Chroma → Neo4j

### 第一階段：Chroma

- 零設定，直接在本地運行，無需 Docker
- LangChain 整合最完整，適合快速驗證
- 用於語義搜尋：將條文向量化後，找出與使用者問題最相關的條文

```python
from langchain_chroma import Chroma
vectorstore = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
```

### 第二階段：Neo4j（驗證完成後替換）

- 內建向量索引（Vector Index，5.x 版後支援）
- 可同時處理向量搜尋與圖遍歷，不需維護兩套系統
- 適合生產環境

---

## 圖資料庫：NetworkX → Neo4j

法條 JSON 本身天生就是一個圖結構：

```
法律 (pcode)
  └── 編/章/節 (divisions)
        └── 條文 (articles)
              └── 引用其他條文 (cross-references，用 regex 從條文內容抽取)
```

### 第一階段：NetworkX

- 純 Python in-memory 圖，零設定
- 適合快速驗證 LangGraph agent 邏輯
- 缺點：不持久化，重啟後需重新建圖
- 節點與邊的屬性以 TypedDict 定義，提供 mypy 型別安全

節點型態：`Law`（id = pcode）、`Article`（id = `{pcode}#{article_no}`）

邊型態（`relation` 屬性）：
- `"contains"`：Law → Article
- `"cites"`：Article → Article，附帶 `citation_type`（見 `CitationType`）

詳細實作見 `src/ingestion/law_graph/CLAUDE.md`。

### 第二階段：Neo4j（與向量資料庫合併）

- Cypher 查詢語言，適合複雜的關係查詢
- LangChain 原生支援（`langchain_neo4j`）
- 與向量搜尋共用同一個資料庫，資料只需存一份

---

## 兩階段規劃原因

| | 第一階段 | 第二階段 |
|---|---|---|
| **向量搜尋** | Chroma | Neo4j 內建向量索引 |
| **圖遍歷** | NetworkX | Neo4j |
| **目標** | 驗證 LangGraph agent 邏輯與資料流程 | 生產環境品質 |
| **設定難度** | 低 | 需要 Docker + 學 Cypher |

先用 Chroma + NetworkX 讓 agent 跑起來，確認 graph 流程正確後，再整體遷移至 Neo4j，避免一開始就卡在基礎設施設定。

---

## Tool Node 設計方向

```
Tool 1: semantic_search_articles(query)      → Chroma 語義搜尋，找概念相關條文
Tool 2: get_related_articles(pcode, art_no)  → NetworkX 圖遍歷，追蹤引用關係
Tool 3: list_chapter_articles(pcode, chapter) → NetworkX 導航章節結構
```

---

# LangGraph 規劃

## State 設計

```python
class LawSearchingState(TypedDict):
    """LawSearchingState 紀錄"""

    messages: Annotated[BaseMessage, add_messages]
    """messages 紀錄整個 Graph 的對話紀錄"""

    judgment_api_token: str
    """司法院 API 登入 token，由啟動時的 login node 寫入，供判決書工具使用"""
```

## Longterm Memory 設計

## Graph 設計

## Node 設計

### 一般 Node

#### login_node

- Graph 啟動時的**第一個 node**，不由 LLM 呼叫
- 從 `.env` 讀取 `JUDGMENT_API_USERNAME` / `JUDGMENT_API_PASSWORD`
- 呼叫司法院 API 取得 token，寫入 `State.judgment_api_token`
- 登入失敗則拋出例外，中止 graph

```
.env
  JUDGMENT_API_USERNAME=xxx
  JUDGMENT_API_PASSWORD=xxx
  GEMINI_API_KEY=xxx
  TAVILY_API_KEY=xxx
```

### tool Node

#### 法條工具（全國法規資料庫 - 法條）

資料來源：全國法規資料庫 ZIP（預處理後存入 Chroma + NetworkX）

| Tool | 輸入 | 說明 |
|---|---|---|
| `search_laws(query)` | 自然語言 | 語義搜尋相關法律，返回法律名稱 + pcode 清單 |
| `search_law_articles(query)` | 自然語言 | 語義搜尋具體條文內容 |
| `get_law_articles(pcode, chapter?)` | pcode | 取得某法律完整條文（可只取某章） |
| `get_related_articles(pcode, article_no)` | 條文編號 | NetworkX 圖遍歷，找引用/被引用的條文 |

> **pcode**：全國法規資料庫每部法律的唯一識別碼，例如憲法為 `A0000001`

---

#### 命令工具（全國法規資料庫 - 命令）

資料來源：全國法規資料庫 ZIP（與法條分開，預處理後存入 Chroma + NetworkX）

| Tool | 輸入 | 說明 |
|---|---|---|
| `search_orders(query)` | 自然語言 | 語義搜尋相關行政命令，返回命令名稱 + pcode 清單 |
| `search_order_articles(query)` | 自然語言 | 語義搜尋命令中的具體條文 |
| `get_order_content(pcode)` | pcode | 取得特定命令全文 |

---

#### 判決書工具（司法院）

資料來源：司法院裁判書查詢網站（https://judgment.judicial.gov.tw/FJUD/default.aspx）

司法院 API 無內建搜尋功能，搜尋改用 Tavily 指定網域查詢；取得判決書全文則使用司法院開放 API。
帳號密碼存於 `.env`，token 由 `login_node` 在啟動時寫入 State，工具從 State 取用。

| Tool | 輸入 | 說明 |
|---|---|---|
| `search_judgments(query)` | 自然語言 | Tavily 搜尋司法院網站，返回相關判決書 ID |
| `get_judgment(judgment_id)` | 判決書 ID | 從 State 取 token，呼叫司法院 API 取得判決書全文 |

### Human in the loop Node
