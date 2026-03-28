from __future__ import annotations

from infrastructure.spreadsheet.base_sheet import BaseSheet
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository

HEADER_ROW = 3


class HomeShipmentSheet(BaseSheet):
    def __init__(self, repo: BaseSheetsRepository, sheet_id: str, sheet_name: str) -> None:
        super().__init__(repo=repo, sheet_id=sheet_id, sheet_name=sheet_name, header_row=HEADER_ROW)

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
