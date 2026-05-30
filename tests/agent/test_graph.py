from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, HumanMessage

from agent.graph import _route, build_graph, login_node
from agent.state import LawSearchingState


# --- login_node ---

def test_login_node_sets_empty_token() -> None:
    state: LawSearchingState = {
        "messages": [],
        "judgment_api_token": "",
    }
    result = login_node(state)
    assert result["judgment_api_token"] == ""


def test_login_node_always_overwrites_existing_token() -> None:
    state: LawSearchingState = {
        "messages": [],
        "judgment_api_token": "old-token",
    }
    result = login_node(state)
    assert result["judgment_api_token"] == ""


# --- _route ---

def test_route_returns_tools_when_tool_calls_present() -> None:
    ai_msg = AIMessage(
        content="",
        tool_calls=[
            {
                "id": "call_1",
                "name": "search_law_articles",
                "args": {"query": "侵權"},
                "type": "tool_call",
            }
        ],
    )
    state: LawSearchingState = {
        "messages": [ai_msg],
        "judgment_api_token": "",
    }
    assert _route(state) == "tools"


def test_route_returns_end_when_no_tool_calls() -> None:
    ai_msg = AIMessage(content="這是最終回答。")
    state: LawSearchingState = {
        "messages": [ai_msg],
        "judgment_api_token": "",
    }
    assert _route(state) == "__end__"


def test_route_returns_end_for_human_message() -> None:
    state: LawSearchingState = {
        "messages": [HumanMessage(content="問題")],
        "judgment_api_token": "",
    }
    assert _route(state) == "__end__"


# --- build_graph（整合：mock LLM）---

def _make_mock_llm(response: AIMessage) -> MagicMock:
    bound = MagicMock()
    bound.invoke.return_value = response
    llm = MagicMock()
    llm.bind_tools.return_value = bound
    return llm


def test_graph_simple_response_sets_token_and_returns_answer() -> None:
    mock_llm = _make_mock_llm(AIMessage(content="找到民法第184條。"))
    graph = build_graph(mock_llm, [])

    result = graph.invoke(
        {"messages": [HumanMessage(content="侵權相關法條")]}
    )

    assert result["judgment_api_token"] == ""
    assert result["messages"][-1].content == "找到民法第184條。"


def test_graph_tool_call_then_final_answer() -> None:
    from langchain_core.tools import tool as make_tool

    @make_tool
    def search_law_articles(query: str) -> str:
        """語意搜尋法條。"""
        return "民法 第 184 條\n因故意或過失..."

    tool_call_msg = AIMessage(
        content="",
        tool_calls=[
            {
                "id": "call_1",
                "name": "search_law_articles",
                "args": {"query": "侵權"},
                "type": "tool_call",
            }
        ],
    )
    final_msg = AIMessage(content="根據民法第184條...")

    bound = MagicMock()
    bound.invoke.side_effect = [tool_call_msg, final_msg]
    mock_llm = MagicMock()
    mock_llm.bind_tools.return_value = bound

    graph = build_graph(mock_llm, [search_law_articles])  # type: ignore[arg-type]
    result = graph.invoke(
        {"messages": [HumanMessage(content="侵權")]}
    )

    assert result["messages"][-1].content == "根據民法第184條..."
    assert bound.invoke.call_count == 2
