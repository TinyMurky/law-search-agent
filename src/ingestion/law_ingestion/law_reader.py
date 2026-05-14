import json
from pathlib import Path

from .law import Law


class LawReader:
    """從 ChLaw.json 載入所有法律並回傳 Law 物件清單"""

    def __init__(self, json_path: str | Path) -> None:
        self._path = Path(json_path)

    def load(self) -> list[Law]:
        """讀取 JSON 檔，回傳 list[Law]"""
        raw = self._path.read_text(encoding="utf-8-sig")
        data = json.loads(raw)
        return [Law.model_validate(item) for item in data["Laws"]]

    def build_name_to_pcode(self, laws: list[Law]) -> dict[str, str]:
        """以 law_name 為 key、pcode 為 value 建立 lookup table"""
        return {law.law_name: law.pcode for law in laws}
