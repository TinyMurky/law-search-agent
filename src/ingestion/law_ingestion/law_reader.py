import json
from pathlib import Path

from .law import Law


class LawReader:
    """從 ChLaw.json 載入所有法律並回傳 Law 物件清單"""

    def __init__(self, json_path: str | Path) -> None:
        """指定 ChLaw.json 的路徑。

        Args:
            json_path (str | Path): JSON 檔案路徑。
        """
        self._path = Path(json_path)

    def load(self) -> list[Law]:
        """讀取 JSON 檔，回傳 list[Law]。

        Returns:
            list[Law]: 解析後的法律清單。
        """
        raw = self._path.read_text(encoding="utf-8-sig")
        data = json.loads(raw)
        return [Law.model_validate(item) for item in data["Laws"]]

    def build_name_to_pcode(self, laws: list[Law]) -> dict[str, str]:
        """以 law_name 為 key、pcode 為 value 建立 lookup table。

        Args:
            laws (list[Law]): 已載入的法律清單。

        Returns:
            dict[str, str]: law_name 對 pcode 的對照表。
        """
        return {law.law_name: law.pcode for law in laws}
