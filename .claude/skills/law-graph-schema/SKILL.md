---
name: law-graph-schema
description: >
  台灣法律知識圖譜的 schema 參考文件。定義法律圖中所有 Node、Edge 與
  Property 的規格，包含法學依據與實作階段標記。當使用者詢問「法律
  之間有什麼關係」、「條文引用如何建模」、「圖裡有哪些節點」，
  或 AI agent 需要知道該建立哪種 node/edge/property 時，必須參照此
  skill。也適用於設計法律資料 ingestion 流程、規劃 NetworkX 或
  Neo4j schema、以及解釋法條語意結構時。
---

# 台灣法律知識圖譜 Schema

## 資料來源

- `raw_data/laws/ChLaw.json`：全國法規資料庫，1,343 部法律
- LawLevel 分布：憲法 9 部、法律 1,334 部
- 詳細節點與邊的法學依據：見 `references/nodes.md`、`references/edges.md`

---

## 實作階段說明

| 標記 | 說明 |
|---|---|
| **Phase 1** | 已實作（NetworkX） |
| **Phase 1.5** | 可在 NetworkX 階段新增，需補充資料來源 |
| **Phase 2** | 待 Neo4j 建置完成後實作（需 LLM 抽取） |

---

## 通用屬性（所有 Node 與 Edge 皆需帶）

```
source_pcode        : str   # 來源法律 pcode，e.g. "B0000001"
source_article_no   : str   # 來源條文，e.g. "第 184 條"；Law node 為 ""
source_paragraph    : str   # 來源項次，e.g. "第 1 項"；無則 ""
law_modified_date   : str   # LawModifiedDate，e.g. "20240101"（法律版本）
created_at          : str   # ISO 8601 系統時間，e.g. "2026-05-20T10:30:00+08:00"
```

---

## Node 一覽

| Node | Phase | ID 格式 | 說明 |
|---|---|---|---|
| `Law` | 1 | `{pcode}` | 一部完整的法律 |
| `Division` | 1.5 | `{pcode}#div#{seq}` | 編／章／節（ArticleType=C）|
| `Article` | 1 | `{pcode}#{article_no}` | 單一條文（ArticleType=A）|
| `LegalSubject` | 2 | `{pcode}#{article_no}#subj#{seq}` | 行為主體 |
| `LegalAct` | 2 | `{pcode}#{article_no}#act#{seq}` | 法律行為 |
| `LegalObject` | 2 | `{pcode}#{article_no}#obj#{seq}` | 法律客體 |
| `Condition` | 2 | `{pcode}#{article_no}#cond#{seq}` | 構成要件 |
| `LegalEffect` | 2 | `{pcode}#{article_no}#effect#{seq}` | 法律效果 |

詳細屬性與法學依據 → `references/nodes.md`

---

## Edge 一覽

### 結構邊（法律內部）

| Edge | Phase | From → To | 說明 |
|---|---|---|---|
| `CONTAINS` | 1 | Law/Division → Division/Article | 包含關係 |
| `CITES` | 1 | Article → Article | 條文引用（已實作）|

### 法律間關係邊

| Edge | Phase | From → To | 說明 |
|---|---|---|---|
| `AMENDS` | 1.5 | Law → Law | 修正關係，e.g. 憲法增修條文 → 憲法 |
| `IMPLEMENTS` | 1.5 | Law → Law | 施行法/細則對應母法 |
| `AUTHORIZED_BY` | 1.5 | Article → Article | 條文授權訂定子法 |
| `SUPERSEDES` | 1.5 | Law → Law | 廢止並取代舊法 |

### 語意邊（Phase 2）

| Edge | Phase | From → To | 說明 |
|---|---|---|---|
| `HAS_SUBJECT` | 2 | Article → LegalSubject | 條文的行為主體 |
| `HAS_ACT` | 2 | Article → LegalAct | 條文規範的法律行為 |
| `HAS_OBJECT` | 2 | Article → LegalObject | 法律行為的客體 |
| `HAS_CONDITION` | 2 | Article → Condition | 條文的構成要件 |
| `HAS_EFFECT` | 2 | Article → LegalEffect | 條文的法律效果 |
| `TRIGGERS` | 2 | Condition → LegalEffect | 要件成就觸發效果 |
| `PENALIZES` | 2 | Article → Article | 罰則條文指向被規範條文 |

詳細屬性與法學依據 → `references/edges.md`

---

## 快速範例

### 民法第 184 條（侵權行為）的完整圖結構

```
# Phase 1（已實作）
Law("B0000001") --CONTAINS--> Article("B0000001#第 184 條")
Article("B0000001#第 184 條") --CITES--> Article("B0000001#第 185 條")

# Phase 2（LLM 抽取後）
Article("B0000001#第 184 條")
  --HAS_CONDITION--> Condition("...#cond#0")  # 故意或過失、不法侵害
  --HAS_SUBJECT-->   LegalSubject("...#subj#0")  # 行為人
  --HAS_OBJECT-->    LegalObject("...#obj#0")    # 他人之權利
  --HAS_EFFECT-->    LegalEffect("...#effect#0") # 損害賠償責任

Condition("...#cond#0") --TRIGGERS--> LegalEffect("...#effect#0")
```

### 憲法與增修條文的關係

```
# Phase 1.5
Law("A0000002") --AMENDS--> Law("A0000001")
# 中華民國憲法增修條文 修正 中華民國憲法
```
