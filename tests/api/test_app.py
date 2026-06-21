from __future__ import annotations

from collections.abc import AsyncIterable
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from fastapi.testclient import TestClient
from langchain_core.documents import Document

from api.app import create_app


def _make_fake_agent(
    *,
    generation: str = "",
    documents: list[Document] | None = None,
    stream_tokens: list[str] | None = None,
) -> MagicMock:
    """建立一個假的 CompiledStateGraph，供 create_app() 注入測試。"""
    agent = MagicMock()
    agent.ainvoke = AsyncMock(
        return_value={
            "generation": generation,
            "documents": documents or [],
        }
    )

    async def _events() -> AsyncIterable[dict[str, Any]]:
        for token in stream_tokens or []:
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": SimpleNamespace(content=token)},
            }
        yield {"event": "on_chain_end", "data": {}}

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
