from __future__ import annotations

from infrastructure.spreadsheet.base_sheet import BaseSheet
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository

HEADER_ROW = 3

# 自宅発送シートのヘッダーは仕入管理シート1行目の内部名を使うため、
# 業務上の列名（仕入管理シート4行目）から読み替える
COLUMN_ALIASES: dict[str, str] = {
    "ASIN": "ASIN_SELL",
    "購入日": "DATE_ORDER",
    "注文番号": "MyUS",
    "商品名": "TITLE_SELL",
    "購入数": "QTY",
    "納品プラン": "INBOUND_PLAN",
}


class HomeShipmentSheet(BaseSheet):
    def __init__(self, repo: BaseSheetsRepository, sheet_id: str, sheet_name: str) -> None:
        super().__init__(repo=repo, sheet_id=sheet_id, sheet_name=sheet_name, header_row=HEADER_ROW)

    def _get_column_index_by_name(self, column_name: str) -> int:
        key = str(column_name).strip()
        alias = COLUMN_ALIASES.get(key)
        if key not in self._header_index_map and alias in self._header_index_map:
            return super()._get_column_index_by_name(alias)
        return super()._get_column_index_by_name(key)

    def get_row_numbers_column(self) -> list[str]:
        return [str(row.get("行番号") or "").strip() for row in self.data if row.get("行番号")]

    def get_values(self, column_name: str) -> list[str]:
        return [str(row.get(column_name) or "").strip() for row in self.data]

    def get_defect_reason_list(self) -> list[str]:
        all_values = self._worksheet.get_all_values()
        reasons: list[str] = []
        for row_values in all_values[1:]:
            if len(row_values) >= 19:
                val = str(row_values[18]).strip()
                if val:
                    reasons.append(val)
        return reasons
