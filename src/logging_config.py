"""共用 logging 設定，供各 src/entrypoints/*/main.py entry point 啟動時呼叫。"""

from __future__ import annotations

import logging

_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def setup_logging(level: int = logging.INFO) -> None:
    """設定全域 logging 格式與等級。

    只設定 root logger 一次即可讓所有模組的 `logging.getLogger(__name__)`
    套用同一份格式；各 entry point 的 `main()` 開頭都要呼叫這個函式，
    否則 `logger.info(...)` 不會印出任何東西
    （root logger 預設只有 WARNING 以上等級才會被 lastResort handler 印出）。

    Args:
        level (int): 全域 log 等級，預設 logging.INFO。
    """
    logging.basicConfig(level=level, format=_LOG_FORMAT)
