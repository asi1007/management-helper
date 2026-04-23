from __future__ import annotations

import logging

from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository

logger = logging.getLogger(__name__)

SALES_SHEET_ID = "1Z3P0iL19r3gA9-NG8x2e_42pGhrEs_wFMLWLbFvReAw"
SALES_SHEET_NAME = "売上/日"
HEADER_ROW_INDEX = 3
REQUIRED_HEADERS = {"ASIN": "", "SKU": "", "fnsku": ""}


class SalesSheet:
    def __init__(self, repo: BaseSheetsRepository) -> None:
        self._repo = repo

    @staticmethod
    def _find_columns(header: list[str]) -> dict[str, int]:
        col_map: dict[str, int] = {}
        for idx, cell in enumerate(header):
            stripped = cell.strip()
            if stripped in REQUIRED_HEADERS and stripped not in col_map:
                col_map[stripped] = idx
        missing = [name for name in REQUIRED_HEADERS if name not in col_map]
        if missing:
            raise ValueError(f"売上/日シートのヘッダーに必要な列が見つかりません: {missing}")
        return col_map

    def load_asin_to_sku_fnsku(self) -> dict[str, dict[str, str]]:
        worksheet = self._repo.open_worksheet(SALES_SHEET_ID, SALES_SHEET_NAME)
        all_values = worksheet.get_all_values()
        header = all_values[HEADER_ROW_INDEX]
        col_map = self._find_columns(header)

        asin_col = col_map["ASIN"]
        sku_col = col_map["SKU"]
        fnsku_col = col_map["fnsku"]

        result: dict[str, dict[str, str]] = {}
        for row_values in all_values[HEADER_ROW_INDEX + 1:]:
            asin = str(row_values[asin_col]).strip() if len(row_values) > asin_col else ""
            sku = str(row_values[sku_col]).strip() if len(row_values) > sku_col else ""
            fnsku = str(row_values[fnsku_col]).strip() if len(row_values) > fnsku_col else ""

            if not asin or asin in result:
                continue
            if sku or fnsku:
                result[asin] = {"sku": sku, "fnsku": fnsku}

        logger.info("売上/日シートからASIN→SKU/fnsku取得: %d件", len(result))
        return result
