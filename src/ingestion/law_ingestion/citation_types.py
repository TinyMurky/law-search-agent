from typing import Literal

CitationType = Literal[
    "range_zhi",  # 第X條至第Y條
    "range_ji",   # 第X條及第Y條
    "self_ref",   # 本法第X條
    "cross_law",  # 民法第X條
    "bare",       # 第X條（無前綴）
    "relative",   # 前條 / 次條
]
