from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository

if TYPE_CHECKING:
    from gspread import Worksheet

logger = logging.getLogger(__name__)

SALES_SHEET_ID = "1Z3P0iL19r3gA9-NG8x2e_42pGhrEs_wFMLWLbFvReAw"
SALES_SHEET_NAME = "売上/日"
HEADER_SEARCH_LIMIT = 30
REQUIRED_HEADERS = ["ASIN", "SKU", "fnsku"]
DELIVERY_CATEGORY_HEADER = "納品分類"


class SalesSheet:
    def __init__(self, repo: BaseSheetsRepository) -> None:
        self._repo = repo
        self._worksheet: Worksheet | None = None

    def _open(self) -> Worksheet:
        if self._worksheet is None:
            self._worksheet = self._repo.open_worksheet(SALES_SHEET_ID, SALES_SHEET_NAME)
        return self._worksheet

    def _load_table(
        self, required: list[str]
    ) -> tuple[dict[str, int], list[list[str]], int]:
        all_values = self._open().get_all_values()
        header_row = self._find_header_row(all_values, required)
        col_map = self._find_columns(all_values[header_row], required)
        return col_map, all_values[header_row + 1:], header_row

    @staticmethod
    def _find_header_row(all_values: list[list[str]], required: list[str]) -> int:
        """必要な列が揃う行を探す。

        行番号を固定していると、集計行の増減でヘッダーがずれたときに静かに壊れる。
        2026-09-14 に 4 行目から 5 行目へ動いて全処理が止まった。
        """
        for index, row in enumerate(all_values[:HEADER_SEARCH_LIMIT]):
            cells = {str(cell).strip() for cell in row}
            if all(name in cells for name in required):
                return index
        raise ValueError(
            f"売上/日シートの先頭{HEADER_SEARCH_LIMIT}行にヘッダーが見つかりません: {required}"
        )

    @staticmethod
    def _find_columns(header: list[str], required: list[str]) -> dict[str, int]:
        col_map: dict[str, int] = {}
        for idx, cell in enumerate(header):
            stripped = cell.strip()
            if stripped in required and stripped not in col_map:
                col_map[stripped] = idx
        missing = [name for name in required if name not in col_map]
        if missing:
            raise ValueError(f"売上/日シートのヘッダーに必要な列が見つかりません: {missing}")
        return col_map

    @staticmethod
    def _cell(row_values: list[str], index: int) -> str:
        return str(row_values[index]).strip() if len(row_values) > index else ""

    def load_asin_to_sku_fnsku(self) -> dict[str, dict[str, str]]:
        col_map, rows, _ = self._load_table(REQUIRED_HEADERS)

        result: dict[str, dict[str, str]] = {}
        for row_values in rows:
            asin = self._cell(row_values, col_map["ASIN"])
            sku = self._cell(row_values, col_map["SKU"])
            fnsku = self._cell(row_values, col_map["fnsku"])

            if not asin or asin in result:
                continue
            if sku or fnsku:
                result[asin] = {"sku": sku, "fnsku": fnsku}

        logger.info("売上/日シートからASIN→SKU/fnsku取得: %d件", len(result))
        return result

    def load_delivery_category_by_asin(self) -> dict[str, str]:
        col_map, rows, header_row = self._load_table([*REQUIRED_HEADERS, DELIVERY_CATEGORY_HEADER])

        result: dict[str, str] = {}
        for row_values in rows:
            asin = self._cell(row_values, col_map["ASIN"])
            category = self._cell(row_values, col_map[DELIVERY_CATEGORY_HEADER])
            if not asin or asin in result or not category:
                continue
            result[asin] = category
        return result

    def write_delivery_category(self, asin: str, category: str) -> list[int]:
        col_map, rows, header_row = self._load_table([*REQUIRED_HEADERS, DELIVERY_CATEGORY_HEADER])
        target = str(asin).strip()
        column_number = col_map[DELIVERY_CATEGORY_HEADER] + 1

        written: list[int] = []
        for offset, row_values in enumerate(rows):
            if self._cell(row_values, col_map["ASIN"]) != target:
                continue
            row_number = header_row + 2 + offset
            self._open().update_cell(row_number, column_number, category)
            written.append(row_number)

        if not written:
            raise ValueError(f"売上/日シートに ASIN {target} の行がありません")
        logger.info("納品分類「%s」を書き込み: ASIN=%s, 行=%s", category, target, written)
        return written
