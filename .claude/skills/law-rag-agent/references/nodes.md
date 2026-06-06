# 各節點詳細設計與程式碼

## analyze_query

### 職責

輸入使用者問題，輸出：
1. `intent`：問題類型（lookup / diagnostic / comparison / procedural）
2. `complexity`：simple / complex
3. `rewritten_queries`：list[SubQuery]，每個帶 strategy 標記

### 分析流程

```
Step 1：intent_chain → intent, complexity, has_judgment_request,
                        has_specific_article, law_name, article_no

Step 2：依 intent + complexity 決定子查詢策略
  ├─ complex 或 comparison → decompose_chain → 多個 SubQuery
  ├─ lookup + 有條號       → law:direct_lookup（直接用 ir 的 law_name/article_no）
  ├─ lookup + 無條號       → hyde_chain → law:hyde（query = 假設條文）
  ├─ diagnostic            → law:graph_expand
  └─ procedural            → rewrite_chain → law:semantic

Step 3：has_judgment_request=True 且清單中沒有 judgment:tavily
        → 補加一個 judgment:tavily SubQuery
```

### 關鍵設計決策

- **HyDE 在 analyze_query 生成**，存入 SubQuery.query，
  retrieve 節點看到 `law:hyde` 時直接搜尋，不再呼叫 LLM
- **has_specific_article** 讓 intent_chain 一次提取條號，
  避免 lookup 需要額外抽取步驟
- **工廠函式** `make_analyze_query_node(llm)` 注入 LLM 依賴，
  與 `make_law_tools(chunk_builder, law_graph)` 風格一致

### 完整程式碼

```python
# src/agent/nodes/analyze_query.py
from __future__ import annotations

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from typing import Literal

from agent.state import AgenticRAGState, SubQuery


# ── Pydantic schemas ──────────────────────────────────────────────────

class IntentResult(BaseModel):
    intent: Literal[
        "lookup", "diagnostic", "comparison", "procedural"
    ] = Field(description="問題的意圖類型")
    complexity: Literal["simple", "complex"] = Field(
        description="simple=單一面向，complex=含多個面向或實體"
    )
    has_judgment_request: bool = Field(
        description="問題是否提到判決書、裁判、案例"
    )
    has_specific_article: bool = Field(
        description=(
            "問題是否同時含法律名稱和條號，如「民法第184條」"
        )
    )
    law_name: str | None = Field(
        default=None,
        description="has_specific_article=True 時填入，如「民法」",
    )
    article_no: str | None = Field(
        default=None,
        description=(
            "has_specific_article=True 時填入，如「第 184 條」"
        ),
    )
    reason: str = Field(description="判斷依據，一句話")


class SubQuerySpec(BaseModel):
    query: str
    strategy: Literal[
        "law:semantic",
        "law:hyde",
        "law:direct_lookup",
        "law:graph_expand",
        "judgment:tavily",
    ]
    law_name: str | None = None
    article_no: str | None = None


class DecomposeResult(BaseModel):
    sub_queries: list[SubQuerySpec]


# ── Prompts ───────────────────────────────────────────────────────────

_INTENT_SYSTEM = """\
你是一個法律問題意圖分類器。
將問題分類為以下類型之一：
- lookup：查詢具體法條內容或法律定義
- diagnostic：描述法律情境，要找對應法條或解決方向
- comparison：比較兩個以上法律概念、條文或法律
- procedural：詢問法律程序或操作步驟

complexity 判斷規則：
- complex：含多個面向（出現「和」「還有」「以及」「同時」，\
或問了多個不同條文/法律）
- simple：只有一個面向

has_specific_article：問題同時出現法律名稱和條號才為 true，
如「民法第 184 條」「刑法第 271 條」。
has_judgment_request：出現「判決」「裁判」「案例」「判例」則為 true。

{format_instructions}
只輸出 JSON，不要其他文字。"""

_DECOMPOSE_SYSTEM = """\
你是一個法律問題分解器。
將問題拆成多個獨立子查詢，每個子查詢選擇最適合的搜尋策略。

策略說明：
- law:semantic：語意搜尋法條（不知道具體條號）
- law:hyde：生成假設條文再語意搜尋（查詢概念性法律定義）
- law:direct_lookup：直接查詢已知條文（問題含具體法律名稱和條號）
- law:graph_expand：語意搜尋後展開引用鏈（描述法律情境，找相關條文群）
- judgment:tavily：搜尋判決書（提到判決、裁判、案例）

law:direct_lookup 時必須填入 law_name（如「民法」）\
和 article_no（如「第 184 條」）。

改寫規則：
1. 每個子查詢應獨立可搜尋，不依賴其他子查詢的結果
2. 補充口語問法對應的法律術語
3. 不同面向拆成不同子查詢，不要把所有問題塞進一個查詢

{format_instructions}
只輸出 JSON，不要其他文字。"""

_HYDE_SYSTEM = """\
你是一個台灣法律條文模擬器。
根據使用者的問題，生成一段「假設的法律條文內容」。
這段內容應該是：如果答案存在於法律條文中，它大概會長什麼樣。

格式要求：
- 長度：3–5 句話
- 語言風格：法律條文的正式書寫風格
- 內容要具體，加入可能相關的構成要件、法律術語、\
法律效果與同義詞
- 不要說「這是假想的」
- 直接輸出假設的條文內容，不要前言"""

_REWRITE_SYSTEM = """\
你是一個法律查詢最佳化器，專門處理台灣法律條文的語意搜尋。
你的任務：把使用者的問題改寫成更適合向量搜尋的形式。

改寫規則：
1. 把口語換成法律文件可能使用的術語
   （例如「被打了」→「不法侵害身體」、\
「借錢不還」→「債務不履行」）
2. 補充問題裡隱含的相關法律概念和關鍵字
3. 擴充可能的同義詞與相關法律術語
4. 輸出長度不超過兩句話
5. 直接輸出改寫後的查詢，不要前言"""


# ── Chain builders ────────────────────────────────────────────────────

def _make_intent_chain(llm: ChatGoogleGenerativeAI):
    parser = JsonOutputParser(pydantic_object=IntentResult)
    prompt = ChatPromptTemplate.from_messages([
        ("system", _INTENT_SYSTEM),
        ("human", "問題：{question}"),
    ])
    return (
        prompt.partial(
            format_instructions=parser.get_format_instructions()
        )
        | llm
        | parser
    )


def _make_decompose_chain(llm: ChatGoogleGenerativeAI):
    parser = JsonOutputParser(pydantic_object=DecomposeResult)
    prompt = ChatPromptTemplate.from_messages([
        ("system", _DECOMPOSE_SYSTEM),
        ("human", "問題：{question}"),
    ])
    return (
        prompt.partial(
            format_instructions=parser.get_format_instructions()
        )
        | llm
        | parser
    )


def _make_hyde_chain(llm: ChatGoogleGenerativeAI):
    prompt = ChatPromptTemplate.from_messages([
        ("system", _HYDE_SYSTEM),
        ("human", "問題：{question}"),
    ])
    return prompt | llm


def _make_rewrite_chain(llm: ChatGoogleGenerativeAI):
    prompt = ChatPromptTemplate.from_messages([
        ("system", _REWRITE_SYSTEM),
        ("human", "問題：{question}"),
    ])
    return prompt | llm


# ── Helper ────────────────────────────────────────────────────────────

def _to_sub_query(spec: SubQuerySpec | dict) -> SubQuery:
    d = (
        spec.model_dump()
        if isinstance(spec, SubQuerySpec)
        else spec
    )
    return SubQuery(
        query=d["query"],
        strategy=d["strategy"],
        law_name=d.get("law_name"),
        article_no=d.get("article_no"),
    )


# ── Node factory ──────────────────────────────────────────────────────

def make_analyze_query_node(llm: ChatGoogleGenerativeAI):
    """建立 analyze_query 節點，注入 LLM 依賴。"""
    intent_chain = _make_intent_chain(llm)
    decompose_chain = _make_decompose_chain(llm)
    hyde_chain = _make_hyde_chain(llm)
    rewrite_chain = _make_rewrite_chain(llm)

    def analyze_query_node(
        state: AgenticRAGState,
    ) -> dict:
        question = state["question"]

        # Step 1：分類意圖與複雜度
        ir = intent_chain.invoke({"question": question})
        intent: str = ir["intent"]
        complexity: str = ir["complexity"]
        is_complex = complexity == "complex"
        print(
            f"[analyze_query] 意圖：{intent}，複雜度：{complexity}，"
            f"has_judgment：{ir['has_judgment_request']}"
        )

        # Step 2：依意圖 + 複雜度決定子查詢策略
        specs: list[SubQuerySpec | dict]

        if is_complex or intent == "comparison":
            raw = decompose_chain.invoke({"question": question})
            specs = raw["sub_queries"]
            print(
                f"[analyze_query] 策略：子查詢分解，"
                f"{len(specs)} 個子查詢"
            )

        elif intent == "lookup" and ir["has_specific_article"]:
            specs = [SubQuerySpec(
                query=question,
                strategy="law:direct_lookup",
                law_name=ir["law_name"],
                article_no=ir["article_no"],
            )]
            print(
                f"[analyze_query] 策略：direct_lookup"
                f"（{ir['law_name']} {ir['article_no']}）"
            )

        elif intent == "lookup":
            hyde_doc = hyde_chain.invoke(
                {"question": question}
            ).content
            specs = [SubQuerySpec(
                query=hyde_doc,
                strategy="law:hyde",
            )]
            print("[analyze_query] 策略：HyDE")

        elif intent == "diagnostic":
            specs = [SubQuerySpec(
                query=question,
                strategy="law:graph_expand",
            )]
            print("[analyze_query] 策略：graph_expand")

        else:  # procedural
            rewritten = rewrite_chain.invoke(
                {"question": question}
            ).content
            specs = [SubQuerySpec(
                query=rewritten,
                strategy="law:semantic",
            )]
            print("[analyze_query] 策略：查詢改寫")

        # Step 3：補判決書子查詢
        strategies = [
            s["strategy"] if isinstance(s, dict) else s.strategy
            for s in specs
        ]
        if ir["has_judgment_request"] and (
            "judgment:tavily" not in strategies
        ):
            specs.append(SubQuerySpec(
                query=question,
                strategy="judgment:tavily",
            ))
            print("[analyze_query] 加入判決書子查詢")

        return {
            "intent": intent,
            "complexity": complexity,
            "rewritten_queries": [_to_sub_query(s) for s in specs],
        }

    return analyze_query_node
```

---

## retrieve

### 職責

依每個 `SubQuery.strategy` 搜尋對應資料源，清空並重建 `documents`。

### 關鍵設計決策

- `law:semantic` 與 `law:hyde` 共用搜尋邏輯：HyDE 假設條文已在
  `analyze_query` 生成並存入 `SubQuery.query`，retrieve 直接搜尋
- `seen: set[str]` 以 `node_id` 去重，同一條文不會重複出現
- `_EXPAND_K = 3`：`law:graph_expand` 每篇搜尋結果最多展開 3 條引用，
  避免熱門條文展開過多文件
- `find_pcode_by_name` 已加入 `NxLawGraph`（線性搜尋 Law 節點，共 1343 個）

### Document metadata 格式

所有文件統一帶以下 metadata，供 `grade_documents` 與 `generate` 使用：

```python
{
    "node_id":    "{pcode}#{article_no}",  # 去重 key
    "pcode":      "B0000001",
    "article_no": "第 184 條",
    "law_name":   "民法",
    "source":     "law",                   # 或 "judgment"（placeholder）
}
```

### 完整程式碼

```python
# src/agent/nodes/retrieve.py
from __future__ import annotations

from typing import cast

from langchain_core.documents import Document

from agent.state import AgenticRAGState
from ingestion.law_graph.nodes import ArticleNodeAttrs
from ingestion.law_graph.nx_law_graph import NxLawGraph
from ingestion.law_vector.chunk_builder import ChunkBuilder

_SEARCH_K = 5
_EXPAND_K = 3


def _search_result_to_doc(r: dict) -> Document:
    return Document(
        page_content=(
            f"【{r['law_name']} {r['article_no']}】\n{r['content']}"
        ),
        metadata={
            "node_id": r["node_id"],
            "pcode": r["node_id"].split("#")[0],
            "article_no": r["article_no"],
            "law_name": r["law_name"],
            "source": "law",
        },
    )


def _article_node_to_doc(
    node_id: str,
    article: ArticleNodeAttrs,
) -> Document:
    return Document(
        page_content=(
            f"【{article['law_name']} {article['article_no']}】\n"
            f"{article['content']}"
        ),
        metadata={
            "node_id": node_id,
            "pcode": article["pcode"],
            "article_no": article["article_no"],
            "law_name": article["law_name"],
            "source": "law",
        },
    )


def make_retrieve_node(
    chunk_builder: ChunkBuilder,
    law_graph: NxLawGraph,
):
    """建立 retrieve 節點，注入 DB 依賴。"""

    def retrieve_node(state: AgenticRAGState) -> dict:
        all_docs: list[Document] = []
        seen: set[str] = set()

        def _add(doc: Document) -> None:
            nid = str(doc.metadata["node_id"])
            if nid not in seen:
                seen.add(nid)
                all_docs.append(doc)

        for sub in state["rewritten_queries"]:
            strategy = sub["strategy"]
            print(f"[retrieve] strategy={strategy}")

            if strategy in ("law:semantic", "law:hyde"):
                for r in chunk_builder.search(
                    sub["query"], k=_SEARCH_K
                ):
                    _add(_search_result_to_doc(r))

            elif strategy == "law:direct_lookup":
                pcode = law_graph.find_pcode_by_name(
                    sub["law_name"] or ""
                )
                if pcode is None:
                    print(
                        f"[retrieve] 找不到 pcode："
                        f"{sub['law_name']}"
                    )
                    continue
                node_id = f"{pcode}#{sub['article_no']}"
                node = law_graph.get_node(node_id)
                if node is None or node["type"] != "article":
                    print(f"[retrieve] 找不到條文：{node_id}")
                    continue
                _add(_article_node_to_doc(
                    node_id, cast(ArticleNodeAttrs, node)
                ))

            elif strategy == "law:graph_expand":
                results = chunk_builder.search(
                    sub["query"], k=_SEARCH_K
                )
                for r in results:
                    _add(_search_result_to_doc(r))
                    pcode = r["node_id"].split("#")[0]
                    article_no = r["node_id"].split("#", 1)[1]
                    cited = law_graph.get_cited_with_edges(
                        pcode, article_no
                    )
                    for cited_id, _ in cited[:_EXPAND_K]:
                        cited_node = law_graph.get_node(cited_id)
                        if (
                            cited_node is not None
                            and cited_node["type"] == "article"
                        ):
                            _add(_article_node_to_doc(
                                cited_id,
                                cast(ArticleNodeAttrs, cited_node),
                            ))

            elif strategy == "judgment:tavily":
                print("[retrieve] judgment:tavily（placeholder）")

        print(f"[retrieve] 共取得 {len(all_docs)} 份文件")
        return {"documents": all_docs}

    return retrieve_node
```

---

## grade_documents

### 職責

過濾 `documents` 中與 `question` 不相關的文件，決定下一步路由。

> **⚠️ TBD：** grader 實作方式（LLM 判斷 vs 向量 threshold）待確認。

### 路由邏輯

```python
def route_after_grade(state: AgenticRAGState) -> str:
    if state["documents"]:
        return "generate"
    if state["retry_count"] < state["max_retries"]:
        return "rewrite_query"
    return "force_end"
```

---

## generate

### 職責

用 `question` 和 `documents` 生成答案，
執行幻覺 grader 和 answer grader 決定路由。

> **⚠️ TBD：** 完整程式碼待實作。grader 是否拆成獨立節點待確認。

### 幻覺 grader

判斷 `generation` 是否有根據於 `documents`。
- 通過 → answer grader
- 不通過 → "regenerate"（`regenerate_count` +1，達上限改走 "rewrite_query"）

### answer grader

判斷 `generation` 是否真正回答了 `question`。
- 通過 → "finish"
- 不通過 → "rewrite_query"

---

## rewrite_query

### 職責

依現有資訊重新改寫查詢，讓下次 retrieve 找到更相關文件。

> **⚠️ TBD：** 完整程式碼待實作。

輸入：`question`（原始問題不變）、`generation`（上一輪答案，可作改寫參考）
輸出：`rewritten_queries`（新的 SubQuery 清單）、`retry_count`（+1）

---

## force_end

### 職責

達到 `max_retries` 且仍無相關文件，生成查無結果說明寫入 `generation`。

說明須包含：
- 告知找不到相關資料
- 建議使用者換個問法或提供更多資訊
- 不得憑空捏造法條或判決書
