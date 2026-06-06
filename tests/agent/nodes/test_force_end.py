from langchain_core.messages import AIMessage

from agent.nodes.force_end import force_end_node


# ── Helpers ───────────────────────────────────────────────────────────

def _state(question: str = "侵權行為的定義？") -> dict:
    return {
        "question": question,
        "intent": "lookup",
        "complexity": "simple",
        "rewritten_queries": [],
        "documents": [],
        "generation": "",
        "retry_count": 3,
        "max_retries": 3,
        "regenerate_count": 0,
        "max_regenerates": 2,
        "halt_reason": "",
        "judgment_api_token": "",
        "messages": [],
    }


# ── Tests ─────────────────────────────────────────────────────────────

def test_generation_contains_question() -> None:
    result = force_end_node(_state("民法第 184 條的要件？"))  # type: ignore[arg-type]
    assert "民法第 184 條的要件？" in str(result["generation"])


def test_halt_reason_set() -> None:
    result = force_end_node(_state())  # type: ignore[arg-type]
    assert result["halt_reason"] == "max_retries_exceeded"


def test_messages_contains_ai_message() -> None:
    result = force_end_node(_state())  # type: ignore[arg-type]
    messages = result["messages"]
    assert len(messages) == 1
    assert isinstance(messages[0], AIMessage)


def test_ai_message_content_matches_generation() -> None:
    result = force_end_node(_state())  # type: ignore[arg-type]
    assert result["messages"][0].content == result["generation"]
