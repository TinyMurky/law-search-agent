from langchain_core.tools import BaseTool, tool


def make_judgment_tools() -> list[BaseTool]:
    """建立判決書搜尋相關工具（API 尚未串接前的 placeholder）。

    Returns:
        list[BaseTool]: search_judgments 與 get_judgment 兩個工具。
    """

    @tool
    def search_judgments(query: str) -> str:
        """搜尋判決書。輸入自然語言，回傳相關判決書 ID 清單。"""
        return "[placeholder] 判決書搜尋功能尚未實作。"

    @tool
    def get_judgment(judgment_id: str) -> str:
        """取得判決書全文。輸入判決書 ID，回傳完整內容。"""
        return "[placeholder] 判決書取得功能尚未實作。"

    return [search_judgments, get_judgment]
