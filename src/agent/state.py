from typing import Annotated, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from agent.strategy_registry import StrategyName


class LawSearchingState(TypedDict):
    """Graph 啟動初期使用的最小狀態，login_node 寫入 token。"""

    messages: Annotated[list[BaseMessage], add_messages]
    judgment_api_token: str


class SubQuery(TypedDict):
    """analyze_query 節點輸出的單一子查詢，對應一種搜尋策略。"""

    query: str
    strategy: StrategyName  # 唯一來源：strategy_registry.StrategyName
    law_name: str | None
    article_no: str | None


class AgenticRAGState(TypedDict):
    """Self-RAG LangGraph 的完整狀態，貫穿 analyze_query 到
    generate 各節點。"""

    # 輸入（整個 Graph 執行期間不變）
    question: str

    # analyze_query 的輸出
    intent: str
    complexity: str
    rewritten_queries: list[SubQuery]

    # retrieve 的輸出（每次 rewrite 時重置）
    documents: list[Document]

    # grade_documents 的輸出
    grade_passed: bool

    # generate 的輸出
    generation: str
    hallucination_passed: bool
    answer_passed: bool

    # 流程控制
    rewrite_count: int
    max_rewrites: int
    regenerate_count: int
    max_regenerates: int

    # 終止原因
    halt_reason: str

    # 認證（login_node 寫入）
    judgment_api_token: str

    # 多輪對話歷史
    messages: Annotated[list[BaseMessage], add_messages]
