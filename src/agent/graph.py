from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, SystemMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from .state import LawSearchingState

_SYSTEM_PROMPT = """\
你是一位專業的法律資訊助理，以嚴謹、客觀的法律專業思維提供資訊。

回答原則：
- 以專業法律角度分析問題，引用相關法條與判決
- 你不是律師，所有回答僅供參考，不構成正式法律意見
- AI 產生的內容可能有誤，重要法律事務請諮詢執業律師
- 每次回答結尾必須附上「【參考資料】」段落，\
列出本次引用的法律名稱與條號\
"""


def login_node(
    state: LawSearchingState,
) -> dict[str, str]:
    """Placeholder: 向司法院 API 登入並取得 token。"""
    print("[login] 司法院 API 登入（placeholder，尚未實作）")
    return {"judgment_api_token": ""}


def _route(
    state: LawSearchingState,
) -> Literal["tools", "__end__"]:
    """Agent 回應有 tool_calls 則繼續查詢，否則結束。"""
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return END  # type: ignore[return-value]


def build_graph(
    llm: BaseChatModel,
    tools: list[BaseTool],
) -> CompiledStateGraph:
    """組裝並編譯 LangGraph agent。"""
    llm_with_tools = llm.bind_tools(tools)

    def agent_node(
        state: LawSearchingState,
    ) -> dict[str, object]:
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            *state["messages"],
        ]
        response = llm_with_tools.invoke(messages)
        return {"messages": [response]}

    tool_node = ToolNode(tools)
    builder: StateGraph = StateGraph(LawSearchingState)
    builder.add_node("login", login_node)
    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)
    builder.add_edge(START, "login")
    builder.add_edge("login", "agent")
    builder.add_conditional_edges(
        "agent", _route, {"tools": "tools", END: END}
    )
    builder.add_edge("tools", "agent")
    return builder.compile()
