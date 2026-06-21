import logging

from logging_config import setup_logging


def test_setup_logging_sets_root_level() -> None:
    """setup_logging 後 root logger 等級應套用傳入的 level。"""
    root = logging.getLogger()
    original_level = root.level
    original_handlers = root.handlers[:]
    try:
        for handler in original_handlers:
            root.removeHandler(handler)

        setup_logging(level=logging.DEBUG)

        assert root.level == logging.DEBUG
        assert len(root.handlers) >= 1
    finally:
        root.setLevel(original_level)
        for handler in root.handlers[:]:
            root.removeHandler(handler)
        for handler in original_handlers:
            root.addHandler(handler)
