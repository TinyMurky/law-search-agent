from typing import Literal, TypedDict

# ── Strategy 型別 ─────────────────────────────────────────────────────
# 新增 strategy 時：
#   1. 在 StrategyName 加入新的 Literal 值
#   2. 在 STRATEGY_REGISTRY 加入對應的 StrategyConfig
#   3. 在 retrieve.py 加入對應的 if/elif 分支
#      （未來可將 retrieve.py 的分支也遷入 retriever 欄位）

StrategyName = Literal[
    "law:semantic",
    "law:hyde",
    "law:direct_lookup",
    "law:graph_expand",
    "judgment:tavily",
]


# ── Per-strategy 設定 ─────────────────────────────────────────────────

class StrategyConfig(TypedDict):
    requires_grading: bool
    # 未來可擴充欄位（勿隨意新增，先討論後再加）：
    #   source: str            # "law" | "judgment"
    #   fallback_strategy: str # rewrite_query fallback 策略
    #   has_score: bool        # 結果是否附帶相似度分數


STRATEGY_REGISTRY: dict[str, StrategyConfig] = {
    # Chroma 語意搜尋，結果需 LLM 判斷相關性
    "law:semantic":      {"requires_grading": True},
    # query 已是 HyDE 假設條文，搜尋路徑與 semantic 相同
    "law:hyde":          {"requires_grading": True},
    # 使用者明確指定條號，不需判斷相關性
    "law:direct_lookup": {"requires_grading": False},
    # Chroma 搜尋 + 引用展開，兩類文件均需 LLM 判斷
    "law:graph_expand":  {"requires_grading": True},
    # Tavily 搜尋判決書（placeholder）
    "judgment:tavily":   {"requires_grading": True},
}
