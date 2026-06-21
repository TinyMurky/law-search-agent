from langgraph.graph.state import CompiledStateGraph

from agent.bootstrap import build_agent_from_env
from agent.state import make_initial_state
from logging_config import setup_logging


def _chat_loop(graph: CompiledStateGraph) -> None:
    """啟動互動式對話迴圈，直到使用者輸入 exit。

    Args:
        graph (CompiledStateGraph): 已編譯的 Self-RAG LangGraph。
    """
    print("\n法律搜尋 Agent 已啟動（輸入 exit 離開）\n")
    while True:
        try:
            user_input = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n離開。")
            break
        if user_input.lower() in ("exit", "quit", "q", ""):
            break
        result = graph.invoke(make_initial_state(user_input))
        answer = result.get("generation") or ""
        if not answer:
            msgs = result.get("messages", [])
            answer = msgs[-1].content if msgs else "（無回應）"
        print(f"\nAgent: {answer}\n")


def main() -> None:
    """建立 Agent 並啟動互動式對話迴圈。"""
    setup_logging()
    graph = build_agent_from_env()
    _chat_loop(graph)


if __name__ == "__main__":
    main()
