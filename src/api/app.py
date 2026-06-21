from __future__ import annotations

from collections.abc import AsyncIterable

from fastapi import FastAPI
from fastapi.sse import EventSourceResponse, ServerSentEvent
from langchain_core.documents import Document
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from agent.state import make_initial_state

_TOKEN_EVENT = "on_chat_model_stream"


class SearchRequest(BaseModel):
    """`/search`、`/search/stream` 共用的請求格式。"""

    query: str


class SourceRef(BaseModel):
    """`/search` 回答所依據的單筆條文來源。"""

    law_name: str
    article_no: str


class SearchResponse(BaseModel):
    """`/search` 的完整回答格式。"""

    answer: str
    sources: list[SourceRef]


def _to_source_refs(documents: list[Document]) -> list[SourceRef]:
    """把 Agent 回傳的文件清單轉成 API 回應用的來源清單。

    Args:
        documents (list[Document]): generate 節點實際使用的文件。

    Returns:
        list[SourceRef]: 每份文件對應的法律名稱與條號。
    """
    return [
        SourceRef(
            law_name=str(doc.metadata.get("law_name", "")),
            article_no=str(doc.metadata.get("article_no", "")),
        )
        for doc in documents
    ]


def create_app(agent: CompiledStateGraph) -> FastAPI:
    """組裝 FastAPI app，把已建立好的 Agent 當依賴注入進來。

    這個函式本身不讀 `.env`、不知道 Agent 怎麼建出來的，agent 由
    呼叫者（`src/cmd/api_server/main.py`）建立後傳入，方便測試時
    換成假的 agent。

    Args:
        agent (CompiledStateGraph): 已編譯完成的 Self-RAG LangGraph。

    Returns:
        FastAPI: 掛好 `/search`、`/search/stream`、`/health` 三個
            endpoint 的 app。
    """
    app = FastAPI()

    @app.post("/search")
    async def search(req: SearchRequest) -> SearchResponse:
        result = await agent.ainvoke(make_initial_state(req.query))
        answer = str(result.get("generation") or "")
        documents = result.get("documents") or []
        return SearchResponse(
            answer=answer,
            sources=_to_source_refs(documents),
        )

    @app.post("/search/stream", response_class=EventSourceResponse)
    async def search_stream(
        req: SearchRequest,
    ) -> AsyncIterable[ServerSentEvent]:
        async for event in agent.astream_events(
            make_initial_state(req.query)
        ):
            if event["event"] == _TOKEN_EVENT:
                token = event["data"]["chunk"].content
                if token:
                    yield ServerSentEvent(raw_data=token)
        yield ServerSentEvent(raw_data="[DONE]")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
