from __future__ import annotations

from langchain_core.messages import AIMessage

from agent.state import AgenticRAGState


def force_end_node(
    state: AgenticRAGState,
) -> dict[str, object]:
    """達到重試上限時的終止節點，生成誠實的查無結果說明。

    Args:
        state (AgenticRAGState): 目前的 Graph 狀態，取用
            question 欄位。

    Returns:
        dict[str, object]: 寫入 generation、halt_reason、messages
            的 State 更新。
    """
    question = state["question"]
    generation = (
        f"抱歉，在多次嘗試後仍找不到足夠的相關法律資訊來回答：\n"
        f"「{question}」\n\n"
        "建議：\n"
        "1. 換個角度重新提問，加入具體的法律名稱或條號\n"
        "2. 確認問題是否屬於台灣現行法律的範疇\n"
        "3. 或直接諮詢律師取得專業意見"
    )
    return {
        "generation": generation,
        "halt_reason": "max_retries_exceeded",
        "messages": [AIMessage(content=generation)],
    }
