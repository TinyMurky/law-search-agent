---
name: law-vector-schema
description: >
  台灣法律知識庫的 Vector DB（Chroma）設計規範。定義 chunks、nodes、
  edges、communities 四個 collection 的資料結構、embedding 策略、
  實作階段，以及如何從向量搜尋結果連回 NetworkX 圖節點。
  當使用者詢問「Vector DB 要怎麼設計」、「某個 collection 要放什麼」、
  「如何從語意搜尋結果取得圖節點」、「Phase 1 / Phase 2 向量化哪些東西」，
  或 AI agent 在實作 Chroma 相關功能前想確認規格時，必須參照此 skill。
  修改 Vector DB 設計時也應更新此 skill。
---

# 台灣法律知識庫 Vector DB Schema

## 分工原則

Vector DB（Chroma）負責**語意查詢**，NetworkX 負責**結構查詢**。
兩者透過 metadata 內的 `node_id` 串接：
向量搜尋命中 → 從 metadata 取出 node_id → 交給 `NxLawGraph` 走圖。

## Embedding Model

**`models/gemini-embedding-001`**（Google）— 取代 text-embedding-004，與 Gemini 同生態系，繁體中文支援佳。

```python
from langchain_google_genai import GoogleGenerativeAIEmbeddings
embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
```

## Collections 總覽

| Collection | Phase | 放什麼 | 用途 |
|---|---|---|---|
| `chunks` | 1 | Article 條文全文 | 語意搜尋具體條文 |
| `nodes` | 1（Law）/ 2（Article） | Law 模板描述 + Article LLM 摘要 | 找「哪部法律」或「條文概念」|
| `edges` | 1（模板）→ 2（context） | CITES 邊描述 | 找兩節點間的引用關係 |
| `communities` | 2 | 條文群落 LLM 摘要 | 回答高層次法律概念查詢 |

各 collection 詳細設計（document 格式、id 規則、metadata、連回 Graph）：
- `references/chunks.md`
- `references/nodes.md`
- `references/edges.md`
- `references/communities.md`

Python 互動範例（建立 collection、語意搜尋、走圖展開）→ `references/retrieval_examples.md`

## 如何修改這份文件

**新增 collection：** 在總覽表加一行，在 `references/` 新增對應的 `<name>.md`。

**修改欄位：** 直接更新對應的 `references/<collection>.md`，同步更新 `references/retrieval_examples.md` 的程式碼。

**Phase 升級（例如 Edge 換成 citation context）：** 在 `references/edges.md` 更新 document 格式，說明所需前置修改。
