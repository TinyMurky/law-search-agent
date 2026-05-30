from agent.tools.judgment import make_judgment_tools


def test_search_judgments_returns_placeholder() -> None:
    tools = make_judgment_tools()
    search = next(t for t in tools if t.name == "search_judgments")
    result = search.invoke({"query": "侵權行為"})
    assert "placeholder" in result


def test_get_judgment_returns_placeholder() -> None:
    tools = make_judgment_tools()
    get = next(t for t in tools if t.name == "get_judgment")
    result = get.invoke({"judgment_id": "12345"})
    assert "placeholder" in result


def test_make_judgment_tools_returns_two_tools() -> None:
    tools = make_judgment_tools()
    names = {t.name for t in tools}
    assert names == {"search_judgments", "get_judgment"}
