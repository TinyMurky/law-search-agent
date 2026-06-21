from collections.abc import Iterator

import httpx
import streamlit as st

_API_URL = "http://localhost:8000/search/stream"
_DATA_PREFIX = "data: "
_EVENT_PREFIX = "event: "
_DONE_SENTINEL = "[DONE]"
_RESET_EVENT_NAME = "reset"


def _iter_sse_lines(query: str) -> Iterator[tuple[str | None, str]]:
    """呼叫 FastAPI 的 /search/stream，逐行解析 SSE 事件。

    純粹的 HTTP client 呼叫，不會 import 或建立 Agent——這個 demo
    跟未來的網頁前端是同一種角色，只透過 FastAPI 取得結果。

    Args:
        query (str): 使用者輸入的問題。

    Returns:
        Iterator[tuple[str | None, str]]: 逐筆 (event 名稱, data 內容)，
            純文字 token 的 event 名稱為 None。
    """
    pending_event: str | None = None
    with httpx.Client(timeout=60.0) as client:
        with client.stream(
            "POST", _API_URL, json={"query": query}
        ) as response:
            for line in response.iter_lines():
                if line.startswith(_EVENT_PREFIX):
                    pending_event = line[len(_EVENT_PREFIX):]
                    continue
                if not line.startswith(_DATA_PREFIX):
                    continue
                yield pending_event, line[len(_DATA_PREFIX):]
                pending_event = None


def _render_answer(
    query: str,
    placeholder: "st.delta_generator.DeltaGenerator",
) -> None:
    """逐 token 更新畫面，並處理 regenerate 時的 reset 控制訊號。

    Self-RAG 的 generate 節點可能因幻覺檢查沒過而重跑，重跑時
    `/search/stream` 會送一個 `event: reset`，這裡收到後要清空
    目前累積的文字重新開始，否則畫面會把被放棄的舊答案也疊加
    顯示出來（這是實測時發現的真實 bug，不是假設情境）。

    Args:
        query (str): 使用者輸入的問題。
        placeholder (st.delta_generator.DeltaGenerator): 用來重新
            渲染累積文字的 Streamlit placeholder。
    """
    accumulated = ""
    for event_name, data in _iter_sse_lines(query):
        if event_name == _RESET_EVENT_NAME:
            accumulated = ""
            continue
        if data == _DONE_SENTINEL:
            break
        accumulated += data
        placeholder.markdown(accumulated)


def main() -> None:
    """渲染 Streamlit demo 介面：輸入問題、串流顯示回答。"""
    st.title("法律搜尋 Agent Demo")
    query = st.text_input("問題")
    if query:
        _render_answer(query, st.empty())


if __name__ == "__main__":
    main()
