from typing import Annotated, Literal, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class LawSearchingState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
    judgment_api_token: str


class SubQuery(TypedDict):
    query: str
    strategy: Literal[
        "law:semantic",
        "law:hyde",
        "law:direct_lookup",
        "law:graph_expand",
        "judgment:tavily",
    ]
    law_name: str | None
    article_no: str | None


class AgenticRAGState(TypedDict):
    # 輸入（整個 Graph 執行期間不變）
    question: str

    # analyze_query 的輸出
    intent: str
    complexity: str
    rewritten_queries: list[SubQuery]

    # retrieve 的輸出（每次 rewrite 時重置）
    documents: list[Document]

    # generate 的輸出
    generation: str

    # 流程控制
    retry_count: int
    max_retries: int
    regenerate_count: int
    max_regenerates: int

    # 終止原因
    halt_reason: str

    # 認證（login_node 寫入）
    judgment_api_token: str

    # 多輪對話歷史
    messages: Annotated[list[BaseMessage], add_messages]
