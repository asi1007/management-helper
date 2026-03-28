from __future__ import annotations

import logging
from typing import Any, Callable, TYPE_CHECKING

import gspread

from infrastructure.spreadsheet.base_row import BaseRow
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository

if TYPE_CHECKING:
    from gspread import Worksheet

logger = logging.getLogger(__name__)


class BaseSheet:
    def __init__(
        self,
        repo: BaseSheetsRepository,
        sheet_id: str,
        sheet_name: str,
        header_row: int = 1,
    ) -> None:
        self._repo = repo
        self._worksheet: Worksheet = repo.open_worksheet(sheet_id, sheet_name)
        self.header_row = header_row
        self.start_row = header_row + 1

        all_values = self._worksheet.get_all_values()
        if len(all_values) < header_row:
            raise ValueError(f'シート "{sheet_name}" にヘッダー行({header_row})がありません')

        header_raw = all_values[header_row - 1]
        self._headers: list[str] = [str(h).strip() for h in header_raw]
        self._header_index_map: dict[str, int] = {}
        for i, key in enumerate(self._headers):
            if key and key not in self._header_index_map:
                self._header_index_map[key] = i

        data_rows = all_values[header_row:]
        self.all_data: list[BaseRow] = [
            BaseRow(
                values=row,
                column_index_resolver=self._get_column_index_by_name,
                row_number=self.start_row + i,
            )
            for i, row in enumerate(data_rows)
        ]
        self.data: list[BaseRow] = list(self.all_data)

    def _get_column_index_by_name(self, column_name: str) -> int:
        key = str(column_name).strip()
        idx = self._header_index_map.get(key)
        if idx is not None:
            return idx
        valid = [h for h in self._headers if h]
        raise ValueError(f'列 "{key}" が見つかりません。ヘッダー: {valid}')

    def get_rows_by_numbers(self, row_numbers: list[int]) -> list[BaseRow]:
        row_set = set(row_numbers)
        rows = [r for r in self.all_data if r.row_number in row_set]
        self.data = rows
        return rows

    def filter(self, column_name: str, values: list[Any]) -> list[BaseRow]:
        col_idx = self._get_column_index_by_name(column_name)
        str_values = {str(v) for v in values}
        filtered = [r for r in self.all_data if str(r[col_idx]) in str_values]
        self.data = filtered
        logger.info("%sでフィルタリング: %d行が見つかりました", column_name, len(filtered))
        return filtered

    def write_cell(self, row_num: int, column_num: int, value: Any) -> None:
        self._worksheet.update_cell(row_num, column_num, value)
        logger.info("%d行目の%d列に書き込みました", row_num, column_num)

    def write_formula(self, row_num: int, column_num: int, formula: str) -> None:
        cell_label = gspread.utils.rowcol_to_a1(row_num, column_num)
        self._worksheet.update_acell(cell_label, formula)
        logger.info("%d行目の%d列に数式を書き込みました", row_num, column_num)

    def write_column_by_func(
        self, column_name: str, value_func: Callable[[BaseRow, int], Any | None]
    ) -> int:
        col_num = self._get_column_index_by_name(column_name) + 1
        count = 0
        for i, row in enumerate(self.data):
            value = value_func(row, i)
            if value is None:
                continue
            if isinstance(value, dict) and value.get("type") == "formula":
                self.write_formula(row.row_number, col_num, value["value"])
            else:
                self.write_cell(row.row_number, col_num, value)
            count += 1
        logger.info("%sを%d行に書き込みました", column_name, count)
        return count
