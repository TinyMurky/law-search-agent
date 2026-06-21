from collections.abc import Iterator

import httpx
import streamlit as st

_API_URL = "http://localhost:8000/search/stream"
_DATA_PREFIX = "data: "
_DONE_SENTINEL = "[DONE]"


def _stream_answer(query: str) -> Iterator[str]:
    """呼叫 FastAPI 的 /search/stream，逐 token 取得回答。

    純粹的 HTTP client 呼叫，不會 import 或建立 Agent——這個 demo
    跟未來的網頁前端是同一種角色，只透過 FastAPI 取得結果。

    Args:
        query (str): 使用者輸入的問題。

    Returns:
        Iterator[str]: 逐個收到的文字片段。
    """
    with httpx.Client(timeout=60.0) as client:
        with client.stream(
            "POST", _API_URL, json={"query": query}
        ) as response:
            for line in response.iter_lines():
                if not line.startswith(_DATA_PREFIX):
                    continue
                token = line[len(_DATA_PREFIX):]
                if token != _DONE_SENTINEL:
                    yield token


def main() -> None:
    """渲染 Streamlit demo 介面：輸入問題、串流顯示回答。"""
    st.title("法律搜尋 Agent Demo")
    query = st.text_input("問題")
    if query:
        st.write_stream(_stream_answer(query))


if __name__ == "__main__":
    main()
