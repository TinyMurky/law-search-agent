from __future__ import annotations

from collections.abc import AsyncIterable
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from langchain_core.documents import Document

from agent.nodes.generate import FINAL_ANSWER_TAG
from api.app import _extract_token_text, create_app


def _token_event(token: Any, run_id: str = "run-1") -> dict[str, Any]:
    """模擬 generate 節點（已打 FINAL_ANSWER_TAG）吐出的串流事件。"""
    return {
        "event": "on_chat_model_stream",
        "tags": [FINAL_ANSWER_TAG],
        "run_id": run_id,
        "data": {"chunk": SimpleNamespace(content=token)},
    }


def _make_fake_agent(
    *,
    generation: str = "",
    documents: list[Document] | None = None,
    stream_tokens: list[Any] | None = None,
    stream_events: list[dict[str, Any]] | None = None,
) -> MagicMock:
    """建立一個假的 CompiledStateGraph，供 create_app() 注入測試。

    `stream_tokens` 是常見情境的捷徑（每個 token 都打上
    `FINAL_ANSWER_TAG`）；如果要模擬「事件沒打標籤該被濾掉」這種
    情境，改用 `stream_events` 直接指定完整事件。
    """
    agent = MagicMock()
    agent.ainvoke = AsyncMock(
        return_value={
            "generation": generation,
            "documents": documents or [],
        }
    )

    events = stream_events
    if events is None:
        events = [_token_event(token) for token in stream_tokens or []]

    async def _events() -> AsyncIterable[dict[str, Any]]:
        for event in events:
            yield event
        yield {"event": "on_chain_end", "tags": [], "data": {}}

    agent.astream_events = lambda *args, **kwargs: _events()
    return agent


def test_health_returns_ok() -> None:
    app = create_app(_make_fake_agent())
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_search_returns_answer_and_sources() -> None:
    documents = [
        Document(
            page_content="...",
            metadata={"law_name": "民法", "article_no": "第 184 條"},
        )
    ]
    agent = _make_fake_agent(generation="這是答案", documents=documents)
    app = create_app(agent)
    client = TestClient(app)

    response = client.post("/search", json={"query": "問題"})

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "這是答案"
    assert body["sources"] == [
        {"law_name": "民法", "article_no": "第 184 條"}
    ]
    agent.ainvoke.assert_awaited_once()


def test_search_stream_returns_sse_tokens() -> None:
    agent = _make_fake_agent(stream_tokens=["根據", "民法"])
    app = create_app(agent)
    client = TestClient(app)

    response = client.post("/search/stream", json={"query": "問題"})

    assert response.status_code == 200
    assert "data: 根據" in response.text
    assert "data: 民法" in response.text
    assert "data: [DONE]" in response.text


def test_search_stream_handles_gemini_content_block_list() -> None:
    """Gemini 串流時 chunk.content 實際是 list of dict，不是 str。"""
    block_content = [{"type": "text", "text": "根據", "index": 0}]
    agent = _make_fake_agent(stream_tokens=[block_content])
    app = create_app(agent)
    client = TestClient(app)

    response = client.post("/search/stream", json={"query": "問題"})

    assert response.status_code == 200
    assert "data: 根據" in response.text


def test_search_stream_filters_out_untagged_chat_model_events() -> None:
    """analyze_query/grader 等節點共用同一顆 llm，不該被當成最終
    答案串流給使用者——這是實際對 Gemini 跑過一次才發現的問題：
    沒過濾的話，intent 分類 JSON、hallucination/answer grader 的
    JSON 都會混進回答裡。"""
    events = [
        {
            "event": "on_chat_model_stream",
            "tags": [],
            "data": {"chunk": SimpleNamespace(content="不該出現的內部訊號")},
        },
        _token_event("正確答案"),
    ]
    agent = _make_fake_agent(stream_events=events)
    app = create_app(agent)
    client = TestClient(app)

    response = client.post("/search/stream", json={"query": "問題"})

    assert response.status_code == 200
    assert "不該出現的內部訊號" not in response.text
    assert "data: 正確答案" in response.text


def test_search_stream_emits_reset_when_generate_reruns() -> None:
    """generate 因幻覺檢查沒過重跑（regenerate）時是不同 run_id，
    使用者實測回報答案整段重複出現過一次，原因就是這裡——重跑前
    後兩個 run_id 不同，要送 `event: reset` 讓客戶端清空重來，
    不能讓兩次的文字疊加显示。"""
    events = [
        _token_event("第一次回答（後來被放棄）", run_id="run-1"),
        _token_event("第二次", run_id="run-2"),
        _token_event("回答", run_id="run-2"),
    ]
    agent = _make_fake_agent(stream_events=events)
    app = create_app(agent)
    client = TestClient(app)

    response = client.post("/search/stream", json={"query": "問題"})

    assert response.status_code == 200
    lines = response.text.splitlines()
    reset_index = next(i for i, line in enumerate(lines) if "reset" in line)
    first_token_index = lines.index("data: 第一次回答（後來被放棄）")
    second_token_index = lines.index("data: 第二次")
    assert first_token_index < reset_index < second_token_index


def test_extract_token_text_passes_through_plain_string() -> None:
    assert _extract_token_text("根據") == "根據"


def test_extract_token_text_joins_text_blocks() -> None:
    content = [
        {"type": "text", "text": "根據", "index": 0},
        {"type": "text", "text": "民法", "index": 1},
    ]
    assert _extract_token_text(content) == "根據民法"


def test_extract_token_text_ignores_non_text_blocks() -> None:
    content = [
        {"type": "tool_use", "id": "abc"},
        {"type": "text", "text": "根據", "index": 0},
    ]
    assert _extract_token_text(content) == "根據"
