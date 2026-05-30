from typing import Literal

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from .state import LawSearchingState


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
        response = llm_with_tools.invoke(state["messages"])
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
