from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from agent.state import AgenticRAGState, SubQuery

# ── Pydantic schemas ──────────────────────────────────────────────────


class IntentResult(BaseModel):
    intent: Literal[
        "lookup",
        "diagnostic",
        "comparison",
        "procedural",
    ] = Field(description="問題的意圖類型")

    complexity: Literal["simple", "complex"] = Field(
        description="simple=單一面向，complex=含多個面向或實體"
    )

    # has_judgment_request 是 true 的話，要去司法院查判例
    has_judgment_request: bool = Field(description="問題是否提到判決書、裁判、案例")

    # has_specific_article 是 true 的話，可以直接進 graph 查法條,
    # 不用進 vector DB 查
    has_specific_article: bool = Field(
        description=("問題是否同時含法律名稱和條號，如「民法第184條」")
    )
    law_name: str | None = Field(
        default=None,
        description="has_specific_article=True 時填入，如「民法」",
    )
    article_no: str | None = Field(
        default=None,
        description=("has_specific_article=True 時填入，如「第 184 條」"),
    )
    reason: str = Field(
        description="判斷各項目的依據，請各項目的決定都要說明,但輸出時串成一句話用句點連接"
    )


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
- lookup：查詢具體法條內容或法律定義, 如: 「民法第 184 條的內容？」「侵權行為的定義？」
- diagnostic：描述法律情境，要找對應法條或解決方向, 如: 「被房東扣押金怎麼辦？」「老闆不付薪水？」
- comparison：比較兩個以上法律概念、條文或法律, 如： 「民事和刑事責任的差異？」
- procedural：詢問法律程序或法律相關的操作步驟, 如遇到某種法律問題時應該要怎麼做, 如: 「如何提起訴訟？」「申請法律扶助的步驟？」

complexity 判斷規則：
- complex：含多個面向（出現「和」「還有」「以及」「同時」，\
或問了多個不同條文/法律）
- simple：只有一個面向

has_specific_article：問題同時出現法律名稱和條號才為 true，
如「民法第 184 條」「刑法第 271 條」。

has_judgment_request：出現「判決」「裁判」「案例」「判例」\
則為 true。

{format_instructions}
只輸出 JSON，不要其他文字。"""

_DECOMPOSE_SYSTEM = """\
你是一個法律問題分解器。
將問題拆成多個獨立子查詢，每個子查詢選擇最適合的搜尋策略。

策略說明：
- law:semantic：語意搜尋法條（不知道具體條號）
- law:hyde：生成假設條文再語意搜尋（查詢概念性法律定義）
- law:direct_lookup：直接查詢已知條文\
（問題含具體法律名稱和條號）
- law:graph_expand：語意搜尋後展開引用鏈\
（描述法律情境，找相關條文群）
- judgment:tavily：搜尋判決書（提到判決、裁判、案例）

law:direct_lookup 時必須填入 law_name（如「民法」）\
和 article_no（如「第 184 條」）。

改寫規則：
1. 每個子查詢應獨立可搜尋，不依賴其他子查詢的結果
2. 補充口語問法對應的法律術語
3. 不同面向拆成不同子查詢，不要把所有問題塞進一個查詢

範例：

問題：「被房東扣押金不還，還有民法第 425 條是什麼？」
輸出：
{{
  "sub_queries": [
    {{
      "query": "房東不當扣押押金的法律依據與返還請求權",
      "strategy": "law:graph_expand"
    }},
    {{
      "query": "民法第 425 條",
      "strategy": "law:direct_lookup",
      "law_name": "民法",
      "article_no": "第 425 條"
    }}
  ]
}}

問題：「公司沒給我加班費，有什麼法條保護？有沒有相關判決？」
輸出：
{{
  "sub_queries": [
    {{
      "query": "勞工加班費請求權 工資不依法給付 勞動基準法",
      "strategy": "law:semantic"
    }},
    {{
      "query": "加班費 勞工 判決 案例",
      "strategy": "judgment:tavily"
    }}
  ]
}}

問題：「什麼是善意取得？」
輸出：
{{
  "sub_queries": [
    {{
      "query": "善意取得制度 動產所有權取得要件 第三人信賴保護",
      "strategy": "law:hyde"
    }}
  ]
}}

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


def _make_intent_chain(
    llm: ChatGoogleGenerativeAI,
) -> Runnable:
    parser = JsonOutputParser(pydantic_object=IntentResult)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _INTENT_SYSTEM),
            ("human", "問題：{question}"),
        ]
    )
    return (
        prompt.partial(format_instructions=parser.get_format_instructions())
        | llm
        | parser
    )


def _make_decompose_chain(
    llm: ChatGoogleGenerativeAI,
) -> Runnable:
    parser = JsonOutputParser(pydantic_object=DecomposeResult)
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _DECOMPOSE_SYSTEM),
            ("human", "問題：{question}"),
        ]
    )
    return (
        prompt.partial(format_instructions=parser.get_format_instructions())
        | llm
        | parser
    )


def _make_hyde_chain(
    llm: ChatGoogleGenerativeAI,
) -> Runnable:
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _HYDE_SYSTEM),
            ("human", "問題：{question}"),
        ]
    )
    return prompt | llm


def _make_rewrite_chain(  # type: ignore[no-untyped-def]
    llm: ChatGoogleGenerativeAI,
):
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", _REWRITE_SYSTEM),
            ("human", "問題：{question}"),
        ]
    )
    return prompt | llm


# ── Helper ────────────────────────────────────────────────────────────


def _to_sub_query(spec: SubQuerySpec) -> SubQuery:
    return SubQuery(
        query=spec.query,
        strategy=spec.strategy,
        law_name=spec.law_name,
        article_no=spec.article_no,
    )


# ── Node factory ──────────────────────────────────────────────────────


def make_analyze_query_node(
    llm: ChatGoogleGenerativeAI,
) -> Callable[[AgenticRAGState], dict[str, object]]:
    """建立 analyze_query 節點，注入 LLM 依賴。"""
    intent_chain = _make_intent_chain(llm)
    decompose_chain = _make_decompose_chain(llm)
    hyde_chain = _make_hyde_chain(llm)
    rewrite_chain = _make_rewrite_chain(llm)

    def analyze_query_node(
        state: AgenticRAGState,
    ) -> dict[str, object]:
        question = state["question"]

        # Step 1：分類意圖與複雜度
        ir: dict[str, object] = intent_chain.invoke({"question": question})
        intent = str(ir["intent"])
        complexity = str(ir["complexity"])
        is_complex = complexity == "complex"
        # print(
        #     f"[analyze_query] 意圖：{intent}，複雜度：{complexity}，"
        #     f"has_judgment：{ir['has_judgment_request']}"
        # )

        print(f"[analyze_query]: 分類意圖與複雜度: {ir}\n")
        # Step 2：依意圖 + 複雜度決定子查詢策略
        specs: list[SubQuerySpec]

        if is_complex or intent == "comparison":
            raw: dict[str, object] = decompose_chain.invoke(
                {"question": question},
            )
            sub_queries: list[dict[str, object]] = raw[
                "sub_queries"
            ]  # type: ignore[assignment]
            specs = []
            for q in sub_queries:
                _ln = str(q["law_name"]) if q.get("law_name") else None
                _an = str(q["article_no"]) if q.get("article_no") else None
                specs.append(
                    SubQuerySpec(
                        query=str(q["query"]),
                        strategy=q["strategy"],
                        law_name=_ln,
                        article_no=_an,
                    )
                )
            print(f"[analyze_query] 策略：子查詢分解，{len(specs)} 個子查詢")

        elif intent == "lookup" and ir["has_specific_article"]:
            _law = str(ir["law_name"]) if ir["law_name"] else None
            _art = str(ir["article_no"]) if ir["article_no"] else None
            specs = [
                SubQuerySpec(
                    query=question,
                    strategy="law:direct_lookup",
                    law_name=_law,
                    article_no=_art,
                )
            ]
            print(
                f"[analyze_query] 策略：direct_lookup"
                f"（{ir['law_name']} {ir['article_no']}）"
            )

        elif intent == "lookup":
            hyde_doc = str(hyde_chain.invoke({"question": question}).content)
            specs = [
                SubQuerySpec(
                    query=hyde_doc,
                    strategy="law:hyde",
                )
            ]
            print("[analyze_query] 策略：HyDE")

        elif intent == "diagnostic":
            specs = [
                SubQuerySpec(
                    query=question,
                    strategy="law:graph_expand",
                )
            ]
            print("[analyze_query] 策略：graph_expand")

        else:  # procedural
            rewritten = str(
                rewrite_chain.invoke(
                    {
                        "question": question,
                    }
                ).content
            )
            specs = [
                SubQuerySpec(
                    query=rewritten,
                    strategy="law:semantic",
                )
            ]
            print("[analyze_query] 策略：查詢改寫")

        # Step 3：補判決書子查詢
        strategies = [s.strategy for s in specs]
        has_judgment = ir["has_judgment_request"]
        if has_judgment and ("judgment:tavily" not in strategies):
            specs.append(
                SubQuerySpec(
                    query=question,
                    strategy="judgment:tavily",
                )
            )
            print("[analyze_query] 加入判決書子查詢")

        return {
            "intent": intent,
            "complexity": complexity,
            "rewritten_queries": [_to_sub_query(s) for s in specs],
        }

    return analyze_query_node
