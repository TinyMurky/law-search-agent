from langchain_core.messages import HumanMessage

from agent.state import make_initial_state


def test_make_initial_state_sets_question() -> None:
    state = make_initial_state("民法第184條是什麼？")
    assert state["question"] == "民法第184條是什麼？"


def test_make_initial_state_seeds_messages_with_human_message() -> None:
    state = make_initial_state("問題")
    assert len(state["messages"]) == 1
    message = state["messages"][0]
    assert isinstance(message, HumanMessage)
    assert message.content == "問題"


def test_make_initial_state_defaults() -> None:
    state = make_initial_state("問題")
    assert state["documents"] == []
    assert state["rewritten_queries"] == []
    assert state["grade_passed"] is False
    assert state["hallucination_passed"] is True
    assert state["answer_passed"] is True
    assert state["rewrite_count"] == 0
    assert state["max_rewrites"] == 3
    assert state["regenerate_count"] == 0
    assert state["max_regenerates"] == 2
