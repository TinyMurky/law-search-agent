#!/usr/bin/env python3
"""驅動 `make chat`，把一批測試問題餵進去，並把每個節點印出的
log 解析成結構化的執行軌跡（execution trace），供 law-agent-e2e-eval
skill 拿來跟「修改前的預測」比對。

只依賴標準函式庫，不需要 uv 環境，可直接用系統 python3 執行：

    python3 .claude/skills/law-agent-e2e-eval/scripts/run_eval.py \\
        --cases .claude/skills/law-agent-e2e-eval/cases/default.json \\
        --label before-fix

執行前提：repo 根目錄已 `make build-chunks`，且 .env 有 GEMINI_API_KEY。
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
_SKILL_DIR = _SCRIPT_DIR.parent
_REPO_ROOT = _SKILL_DIR.parents[2]

_SPLIT_MARKER = "你: "
_FORCE_END_MARKER = "抱歉，在多次嘗試後仍找不到足夠的相關法律資訊"

_PATTERNS = {
    "intent_line": re.compile(r"\[analyze_query\]: 分類意圖與複雜度: (\{.*\})"),
    "analyze_strategy": re.compile(r"\[analyze_query\] 策略：(.+)"),
    "retrieve_strategy": re.compile(r"\[retrieve\] strategy=(.+)"),
    "pcode_miss": re.compile(r"\[retrieve\] 找不到 pcode：(.+)"),
    "article_miss": re.compile(r"\[retrieve\] 找不到條文：(.+)"),
    "retrieve_total": re.compile(r"\[retrieve\] 共取得 (\d+) 份文件"),
    "grade_kept": re.compile(r"\[grade\] 保留 (\d+)/(\d+) 個文件"),
    "rewrite": re.compile(r"\[rewrite\] 第 (\d+) 次重寫，新查詢：(.+?)\.\.\."),
    "generate_done": re.compile(r"\[generate\] 生成完成（(\d+) 字）"),
    "hallucination": re.compile(r"\[generate\] 幻覺檢查：(✓|✗)"),
    "answer_quality": re.compile(r"\[generate\] 回答品質：(✓|✗)"),
}


def _parse_segment(segment: str) -> dict[str, Any]:
    """把單一問題的完整 log 片段解析成結構化執行軌跡。

    解析範圍是「這一輪對話」內所有節點印出的 log，若該輪觸發了
    rewrite_query 重試迴圈，多次 retrieve/grade 的訊號會被攤平
    彙整在同一份 trace 裡（不分次序），細節仍可從 raw_log.txt
    回頭查證。

    Args:
        segment (str): 兩個 "你: " 提示字之間的原始 stdout 內容。

    Returns:
        dict[str, Any]: 結構化的執行軌跡，欄位涵蓋 intent、
            策略、retrieve/grade/generate 各節點訊號與最終回答。
    """
    trace: dict[str, Any] = {
        "intent": None,
        "complexity": None,
        "analyze_strategy_lines": _PATTERNS["analyze_strategy"].findall(
            segment
        ),
        "retrieve_strategies": _PATTERNS["retrieve_strategy"].findall(
            segment
        ),
        "pcode_misses": _PATTERNS["pcode_miss"].findall(segment),
        "article_misses": _PATTERNS["article_miss"].findall(segment),
        "documents_retrieved": [
            int(n) for n in _PATTERNS["retrieve_total"].findall(segment)
        ],
        "grade_results": [
            {"kept": int(k), "total": int(t)}
            for k, t in _PATTERNS["grade_kept"].findall(segment)
        ],
        "rewrite_count": len(_PATTERNS["rewrite"].findall(segment)),
        "hallucination_checks": _PATTERNS["hallucination"].findall(segment),
        "answer_quality_checks": _PATTERNS["answer_quality"].findall(
            segment
        ),
        "force_end": _FORCE_END_MARKER in segment,
        "answer": "",
    }

    intent_match = _PATTERNS["intent_line"].search(segment)
    if intent_match:
        try:
            parsed = ast.literal_eval(intent_match.group(1))
            trace["intent"] = parsed.get("intent")
            trace["complexity"] = parsed.get("complexity")
        except (ValueError, SyntaxError):
            pass

    agent_idx = segment.rfind("Agent: ")
    if agent_idx != -1:
        trace["answer"] = segment[agent_idx + len("Agent: "):].strip()

    return trace


def _build_stdin(questions: list[str]) -> str:
    """把問題清單組成可以餵進 `make chat` 互動迴圈的 stdin 內容。

    Args:
        questions (list[str]): 依序要問的問題。

    Returns:
        str: 每行一個問題，最後加上 "exit" 結束對話迴圈。
    """
    return "\n".join([*questions, "exit"]) + "\n"


def _git_meta() -> dict[str, Any]:
    """記錄目前 repo 的 commit/branch/是否有未 commit 變更。

    Returns:
        dict[str, Any]: 供 before/after 比對時確認跑的是哪個版本。
    """

    def _run(cmd: list[str]) -> str:
        try:
            result = subprocess.run(
                cmd,
                cwd=_REPO_ROOT,
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except (subprocess.CalledProcessError, OSError):
            return ""

    return {
        "commit": _run(["git", "rev-parse", "--short", "HEAD"]),
        "branch": _run(["git", "rev-parse", "--abbrev-ref", "HEAD"]),
        "dirty": bool(_run(["git", "status", "--porcelain"])),
    }


def run_cases(
    cases: list[dict[str, Any]],
    timeout_per_case: int,
) -> tuple[str, list[dict[str, Any]]]:
    """逐一把測試問題餵進 `make chat`，回收 log 並解析成執行軌跡。

    所有問題在同一個 `make chat` session 裡依序送出 ——
    `_chat_loop` 每輪都會重建全新的初始 State，所以同一 session
    內不同問題之間不會互相汙染狀態，這樣做只是為了不用每個問題
    都重新載入一次法規圖與 Chroma（會慢很多）。

    Args:
        cases (list[dict[str, Any]]): 測試案例，至少需含 "question"。
        timeout_per_case (int): 每個問題的逾時秒數預算，用來推算
            整個 subprocess 的總逾時時間。

    Returns:
        tuple[str, list[dict[str, Any]]]: 完整原始輸出，以及每個
            測試案例對應的解析後執行軌跡（與 cases 等長且同序）。
    """
    questions = [str(c["question"]) for c in cases]
    stdin_text = _build_stdin(questions)
    timeout = timeout_per_case * len(questions) + 60

    try:
        proc = subprocess.run(
            ["make", "chat"],
            cwd=_REPO_ROOT,
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        raw_output = proc.stdout + "\n" + proc.stderr
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        raw_output = f"{stdout}\n{stderr}\n[run_eval] 執行逾時，已強制中止"
        print("✗ make chat 執行逾時，已儲存部分輸出供除錯", file=sys.stderr)

    segments = raw_output.split(_SPLIT_MARKER)[1:]
    # chat loop 在讀最後一行 "exit" 之前也會印一次 "你: "，
    # 所以正常情況下 segments 比問題數多 1（最後一段是空的）。
    if len(segments) != len(questions) + 1:
        print(
            f"⚠️  預期 {len(questions)} 筆回應，"
            f"實際解析出 {max(len(segments) - 1, 0)} 筆，"
            "請檢查 raw_log.txt 確認是否提早中斷（例如 Chroma 未建立、"
            "API key 未設定、或某一題卡住觸發逾時）",
            file=sys.stderr,
        )

    traces = []
    for case, segment in zip(cases, segments):
        trace = _parse_segment(segment)
        trace["id"] = case.get("id")
        trace["question"] = case.get("question")
        traces.append(trace)

    return raw_output, traces


def main() -> None:
    """解析參數、執行測試案例、把結果寫進 runs/<run_id>/。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases",
        required=True,
        help="測試案例 JSON 檔路徑（相對於 repo 根目錄或絕對路徑）",
    )
    parser.add_argument(
        "--label",
        default=None,
        help="run 目錄的自訂標籤，例如 before-prompt-fix",
    )
    parser.add_argument(
        "--timeout-per-case",
        type=int,
        default=90,
        help="每個問題的逾時秒數預算，預設 90 秒",
    )
    args = parser.parse_args()

    cases_path = Path(args.cases)
    if not cases_path.is_absolute():
        cases_path = _REPO_ROOT / cases_path
    cases = json.loads(cases_path.read_text(encoding="utf-8"))["cases"]

    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    if args.label:
        run_id = f"{run_id}-{args.label}"
    run_dir = _SKILL_DIR / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"執行 {len(cases)} 筆測試案例（逐一送進 make chat）...")
    raw_output, traces = run_cases(cases, args.timeout_per_case)

    (run_dir / "raw_log.txt").write_text(raw_output, encoding="utf-8")
    (run_dir / "trace.json").write_text(
        json.dumps(traces, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (run_dir / "meta.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "cases_file": str(cases_path),
                "git": _git_meta(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"\n完成。結果輸出至：{run_dir}")
    for trace in traces:
        flag = " ⚠️ force_end" if trace["force_end"] else ""
        print(
            f"  - {trace['id']}：strategies="
            f"{trace['retrieve_strategies']}{flag}"
        )


if __name__ == "__main__":
    main()
