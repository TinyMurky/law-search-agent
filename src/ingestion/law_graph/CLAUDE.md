# Law Graph 模組說明

## 職責

將 `list[Law]`（已由 `CitationExtractor` 填好 `cited_articles`）建成
in-memory 有向圖（`NxLawGraph`），並提供結構化查詢介面。

---

## Package 結構

```
law_graph/
├── __init__.py              # 對外匯出所有 public types
├── builder.py               # LawGraphBuilder：list[Law] → NxLawGraph
├── protocol.py              # LawGraphProtocol：查詢介面定義
├── nx_law_graph.py          # NxLawGraph：NetworkX 實作
├── nodes/
│   ├── __init__.py
│   ├── law_node_attrs.py    # LawNodeAttrs TypedDict
│   └── article_node_attrs.py# ArticleNodeAttrs TypedDict
└── edges/
    ├── __init__.py
    ├── edge_protocol.py     # EdgeAttrsProtocol：通用欄位介面
    ├── contains.py          # ContainsEdgeAttrs TypedDict
    └── cites.py             # CitesEdgeAttrs TypedDict
```

**呼叫端必須先跑完 `CitationExtractor` 再呼叫 `LawGraphBuilder`，
否則 CITES 邊不會被建立。** 完整流程見 `law_ingestion/CLAUDE.md`。

---

## 節點 ID 格式

| 節點型態 | ID 格式 | 範例 |
|---|---|---|
| Law | `{pcode}` | `B0000001` |
| Article | `{pcode}#{article_no}` | `B0000001#第 1 條` |

`article_no` 使用阿拉伯數字加空格（如 `第 184 條`），與原始 JSON 的
`ArticleNo` 欄位相同。

---

## 邊的 relation 屬性

| 邊型態 | relation 值 | From → To | Phase |
|---|---|---|---|
| CONTAINS | `"contains"` | Law → Article | 1（已實作）|
| CITES | `"cites"` | Article → Article | 1（已實作）|

Phase 1.5/2 新邊（AMENDS、IMPLEMENTS 等）加入時，只需在 `edges/` 新增
對應的 TypedDict，**不需修改 Protocol 或 NxLawGraph**，直接傳新 relation
字串給 `get_related()` 即可。

---

## TypedDict 設計

節點和邊的屬性使用 TypedDict 而非 BaseModel/dataclass。

**理由：** NetworkX 的 `add_node` / `add_edge` 接受 `**kwargs`，屬性以
純 dict 儲存。TypedDict 提供完整的 mypy 靜態型別支援，runtime 開銷為零。

所有邊的 TypedDict 均包含通用欄位（`EdgeAttrsProtocol` 列出）：

```
source_pcode        — 來源法律 pcode
source_article_no   — 來源條文；Law 節點發出的邊填 ""
source_paragraph    — 來源項次；目前均填 ""
law_modified_date   — 法律版本日期
created_at          — 建圖時的 ISO 8601 UTC 時間
```

### ContainsEdgeAttrs

```python
{
    "relation": "contains",
    "source_pcode": ...,
    "source_article_no": "",
    "source_paragraph": "",
    "law_modified_date": ...,
    "created_at": ...,
}
```

### CitesEdgeAttrs

```python
{
    "relation": "cites",
    "citation_type": CitationType,  # 見下方
    "source_pcode": ...,
    "source_article_no": ...,
    "source_paragraph": "",
    "law_modified_date": ...,
    "created_at": ...,
}
```

---

## CitationType

定義於 `law_ingestion/citation_types.py`（被 `Article.cited_articles` 和
`CitesEdgeAttrs` 共用）：

| 值 | 條文原文型態 |
|---|---|
| `"range_zhi"` | 第X條至第Y條 |
| `"range_ji"` | 第X條及第Y條 |
| `"self_ref"` | 本法第X條 |
| `"cross_law"` | 民法第X條（跨法律） |
| `"bare"` | 第X條（無前綴，同法引用） |
| `"relative"` | 前條 / 次條 |

---

## Protocol 設計

`LawGraphProtocol` 只定義一個通用方法：

```python
def get_related(
    node_id: str,
    relation: str,
    direction: Literal["out", "in"] = "out",
) -> list[str]:
    ...
```

**為何只有一個方法：** 新增 edge type 時不需修改 Protocol，呼叫端直接傳入
新的 `relation` 字串即可。避免 Protocol 隨 Phase 1.5 / 2 的邊膨脹。

---

## NxLawGraph API

```python
# 通用查詢（低層）
graph.get_related(node_id, relation, direction="out")

# 語意化便利方法
graph.get_cited_articles(pcode, article_no)   # cites 出邊
graph.get_citing_articles(pcode, article_no)  # cites 入邊
graph.get_law_articles(pcode)                 # contains 出邊
```

`get_citing_articles` 使用 `in_edges` 過濾 `relation="cites"`，
不使用 `predecessors()`，避免把 CONTAINS 邊的 Law 節點誤算進來。

---

## LawGraphBuilder 使用範例

```python
reader = LawReader("raw_data/laws/ChLaw.json")
laws = reader.load()
extractor = CitationExtractor(reader.build_name_to_pcode(laws))
for law in laws:
    extractor.extract_from_law(law)

graph = LawGraphBuilder().build(laws)
articles = graph.get_law_articles("B0000001")
cited = graph.get_cited_articles("B0000001", "第 184 條")
```
