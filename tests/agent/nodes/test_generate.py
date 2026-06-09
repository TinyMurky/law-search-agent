from unittest.mock import MagicMock, patch

import pytest
from langchain_core.documents import Document
from langchain_core.messages import AIMessage

from agent.nodes.generate import make_generate_node, route_after_generate

_MOD = "agent.nodes.generate"


# ── Helpers ───────────────────────────────────────────────────────────

def _doc(content: str = "民法第 184 條條文") -> Document:
    return Document(page_content=content, metadata={"node_id": "B#第 1 條"})


def _hall_result(score: str, reason: str = "test") -> dict:
    return {"score": score, "reason": reason}


def _ans_result(score: str, missing: str = "none") -> dict:
    return {"score": score, "missing": missing}


def _state(
    documents: list[Document] | None = None,
    hallucination_passed: bool = True,
    regenerate_count: int = 0,
    max_regenerates: int = 2,
) -> dict:
    return {
        "question": "侵權行為的定義？",
        "intent": "lookup",
        "complexity": "simple",
        "rewritten_queries": [],
        "documents": documents or [_doc()],
        "grade_passed": True,
        "generation": "",
        "hallucination_passed": hallucination_passed,
        "answer_passed": True,
        "rewrite_count": 0,
        "max_rewrites": 3,
        "regenerate_count": regenerate_count,
        "max_regenerates": max_regenerates,
        "halt_reason": "",
        "judgment_api_token": "",
        "messages": [],
    }


@pytest.fixture
def llm() -> MagicMock:
    return MagicMock()


# ── generate_node ─────────────────────────────────────────────────────

def test_generation_stored_in_state(llm: MagicMock) -> None:
    mock_gen = MagicMock()
    mock_gen.invoke.return_value = "答案文字"
    mock_hall = MagicMock()
    mock_hall.invoke.return_value = _hall_result("yes")
    mock_ans = MagicMock()
    mock_ans.invoke.return_value = _ans_result("yes")

    with (
        patch(f"{_MOD}._make_generate_chain", return_value=mock_gen),
        patch(
            f"{_MOD}._make_hallucination_grader_chain",
            return_value=mock_hall,
        ),
        patch(
            f"{_MOD}._make_answer_grader_chain", return_value=mock_ans
        ),
    ):
        node = make_generate_node(llm)
        result = node(_state())

    assert result["generation"] == "答案文字"


def test_hallucination_passed_true_stored(llm: MagicMock) -> None:
    mock_gen = MagicMock()
    mock_gen.invoke.return_value = "答案"
    mock_hall = MagicMock()
    mock_hall.invoke.return_value = _hall_result("yes")
    mock_ans = MagicMock()
    mock_ans.invoke.return_value = _ans_result("yes")

    with (
        patch(f"{_MOD}._make_generate_chain", return_value=mock_gen),
        patch(
            f"{_MOD}._make_hallucination_grader_chain",
            return_value=mock_hall,
        ),
        patch(
            f"{_MOD}._make_answer_grader_chain", return_value=mock_ans
        ),
    ):
        node = make_generate_node(llm)
        result = node(_state())

    assert result["hallucination_passed"] is True
    assert result["answer_passed"] is True


def test_hallucination_fail_skips_answer_grader(llm: MagicMock) -> None:
    mock_gen = MagicMock()
    mock_gen.invoke.return_value = "幻覺答案"
    mock_hall = MagicMock()
    mock_hall.invoke.return_value = _hall_result("no", "包含臆測")
    mock_ans = MagicMock()

    with (
        patch(f"{_MOD}._make_generate_chain", return_value=mock_gen),
        patch(
            f"{_MOD}._make_hallucination_grader_chain",
            return_value=mock_hall,
        ),
        patch(
            f"{_MOD}._make_answer_grader_chain", return_value=mock_ans
        ),
    ):
        node = make_generate_node(llm)
        result = node(_state())

    mock_ans.invoke.assert_not_called()
    assert result["hallucination_passed"] is False
    assert result["answer_passed"] is True  # 預設值，未被覆寫


def test_regenerate_count_increments_on_hallucination_retry(
    llm: MagicMock,
) -> None:
    mock_gen = MagicMock()
    mock_gen.invoke.return_value = "答案"
    mock_hall = MagicMock()
    mock_hall.invoke.return_value = _hall_result("yes")
    mock_ans = MagicMock()
    mock_ans.invoke.return_value = _ans_result("yes")

    # 模擬上次幻覺失敗（hallucination_passed=False）進入 regenerate
    with (
        patch(f"{_MOD}._make_generate_chain", return_value=mock_gen),
        patch(
            f"{_MOD}._make_hallucination_grader_chain",
            return_value=mock_hall,
        ),
        patch(
            f"{_MOD}._make_answer_grader_chain", return_value=mock_ans
        ),
    ):
        node = make_generate_node(llm)
        result = node(_state(
            hallucination_passed=False,
            regenerate_count=0,
        ))

    assert result["regenerate_count"] == 1


def test_first_generate_does_not_increment_regenerate_count(
    llm: MagicMock,
) -> None:
    mock_gen = MagicMock()
    mock_gen.invoke.return_value = "答案"
    mock_hall = MagicMock()
    mock_hall.invoke.return_value = _hall_result("yes")
    mock_ans = MagicMock()
    mock_ans.invoke.return_value = _ans_result("yes")

    # 初次呼叫：hallucination_passed=True（非 regenerate）
    with (
        patch(f"{_MOD}._make_generate_chain", return_value=mock_gen),
        patch(
            f"{_MOD}._make_hallucination_grader_chain",
            return_value=mock_hall,
        ),
        patch(
            f"{_MOD}._make_answer_grader_chain", return_value=mock_ans
        ),
    ):
        node = make_generate_node(llm)
        result = node(_state(
            hallucination_passed=True,
            regenerate_count=0,
        ))

    assert result["regenerate_count"] == 0


def test_aimage_always_in_messages(llm: MagicMock) -> None:
    mock_gen = MagicMock()
    mock_gen.invoke.return_value = "答案文字"
    mock_hall = MagicMock()
    mock_hall.invoke.return_value = _hall_result("yes")
    mock_ans = MagicMock()
    mock_ans.invoke.return_value = _ans_result("yes")

    with (
        patch(f"{_MOD}._make_generate_chain", return_value=mock_gen),
        patch(
            f"{_MOD}._make_hallucination_grader_chain",
            return_value=mock_hall,
        ),
        patch(
            f"{_MOD}._make_answer_grader_chain", return_value=mock_ans
        ),
    ):
        node = make_generate_node(llm)
        result = node(_state())

    msgs = result["messages"]
    assert len(msgs) == 1
    assert isinstance(msgs[0], AIMessage)
    assert msgs[0].content == "答案文字"


# ── route_after_generate ──────────────────────────────────────────────

def _route_state(
    hallucination_passed: bool = True,
    answer_passed: bool = True,
    regenerate_count: int = 0,
    max_regenerates: int = 2,
) -> dict:
    return {
        "hallucination_passed": hallucination_passed,
        "answer_passed": answer_passed,
        "regenerate_count": regenerate_count,
        "max_regenerates": max_regenerates,
    }


def test_route_finish_when_both_pass() -> None:
    state = _route_state(
        hallucination_passed=True, answer_passed=True
    )
    assert route_after_generate(state) == "finish"  # type: ignore[arg-type]


def test_route_regenerate_when_hallucination_fails_under_limit() -> None:
    state = _route_state(
        hallucination_passed=False,
        regenerate_count=1,
        max_regenerates=2,
    )
    assert route_after_generate(state) == "regenerate"  # type: ignore[arg-type]


def test_route_rewrite_when_hallucination_fails_at_limit() -> None:
    state = _route_state(
        hallucination_passed=False,
        regenerate_count=2,
        max_regenerates=2,
    )
    assert route_after_generate(state) == "rewrite_query"  # type: ignore[arg-type]


def test_route_rewrite_when_answer_fails() -> None:
    state = _route_state(
        hallucination_passed=True, answer_passed=False
    )
    assert route_after_generate(state) == "rewrite_query"  # type: ignore[arg-type]
