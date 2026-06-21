from __future__ import annotations

from collections.abc import AsyncIterable
from typing import Any

from fastapi import FastAPI
from fastapi.sse import EventSourceResponse, ServerSentEvent
from langchain_core.documents import Document
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel

from agent.nodes.generate import FINAL_ANSWER_TAG
from agent.state import make_initial_state

_TOKEN_EVENT = "on_chat_model_stream"
_RESET_EVENT_NAME = "reset"


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


def _extract_token_text(content: str | list[Any]) -> str:
    """從 AIMessageChunk.content 取出純文字片段。

    LangChain 的 content 不一定是單純字串：Gemini 在串流時實際
    回傳的是內容區塊組成的 list（例如
    `[{"type": "text", "text": "根據", "index": 0}]`），直接拿來
    當 `ServerSentEvent(raw_data=...)` 會因為不是字串而驗證失敗。
    這裡只取出文字區塊，忽略其他類型（例如 tool call）。

    Args:
        content (str | list[Any]): `AIMessageChunk.content` 原始值。

    Returns:
        str: 串接後的純文字，沒有文字區塊時回傳空字串。
    """
    if isinstance(content, str):
        return content
    return "".join(
        str(item["text"])
        for item in content
        if isinstance(item, dict) and item.get("type") == "text"
    )


async def _stream_final_answer_events(
    agent: CompiledStateGraph,
    query: str,
) -> AsyncIterable[ServerSentEvent]:
    """把 Agent 執行過程中的事件轉成只含「最終答案」的 SSE 事件。

    Self-RAG 的 `generate` 節點可能因幻覺檢查沒過而重跑
    （regenerate），或因答案品質沒過而整輪重新檢索再生成——每次
    重跑都是一次獨立的 LLM run（不同 `run_id`），但全部都打了
    `FINAL_ANSWER_TAG`，不能只憑標籤判斷，否則會把被放棄的舊答案
    也疊加顯示出來（實際對 Gemini 跑過才發現的真實 bug：使用者
    會看到同一題的答案出現兩次）。

    做法：追蹤目前 `run_id`，一旦出現新的 `run_id`，代表前一次的
    內容被放棄，送出一個 `event: reset` 控制訊號，請客戶端清空
    目前顯示的內容再繼續累積——客戶端實作見
    `src/entrypoints/streamlit_demo/main.py`。

    Args:
        agent (CompiledStateGraph): 已編譯完成的 Self-RAG LangGraph。
        query (str): 使用者輸入的問題。

    Returns:
        AsyncIterable[ServerSentEvent]: 文字 token 與 `reset` 控制
            事件混合的串流，結尾固定送出 `[DONE]`。
    """
    current_run_id: str | None = None
    async for event in agent.astream_events(make_initial_state(query)):
        is_token = event["event"] == _TOKEN_EVENT
        is_final_answer = FINAL_ANSWER_TAG in event.get("tags", [])
        if not (is_token and is_final_answer):
            continue

        run_id = event["run_id"]
        if current_run_id is not None and run_id != current_run_id:
            yield ServerSentEvent(event=_RESET_EVENT_NAME, raw_data="")
        current_run_id = run_id

        token = _extract_token_text(event["data"]["chunk"].content)
        if token:
            yield ServerSentEvent(raw_data=token)
    yield ServerSentEvent(raw_data="[DONE]")


def create_app(agent: CompiledStateGraph) -> FastAPI:
    """組裝 FastAPI app，把已建立好的 Agent 當依賴注入進來。

    這個函式本身不讀 `.env`、不知道 Agent 怎麼建出來的，agent 由
    呼叫者（`src/entrypoints/api_server/main.py`）建立後傳入，方便測試時
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
        async for sse_event in _stream_final_answer_events(
            agent, req.query
        ):
            yield sse_event

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
