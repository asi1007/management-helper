from __future__ import annotations

import logging

from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository

logger = logging.getLogger(__name__)

SALES_SHEET_ID = "1Z3P0iL19r3gA9-NG8x2e_42pGhrEs_wFMLWLbFvReAw"
SALES_SHEET_NAME = "売上/日"
HEADER_ROW = 4
ASIN_COL = 0
SKU_COL = 41
FNSKU_COL = 42


class SalesSheet:
    def __init__(self, repo: BaseSheetsRepository) -> None:
        self._repo = repo

    def load_asin_to_sku_fnsku(self) -> dict[str, dict[str, str]]:
        worksheet = self._repo.open_worksheet(SALES_SHEET_ID, SALES_SHEET_NAME)
        all_values = worksheet.get_all_values()

        result: dict[str, dict[str, str]] = {}
        for row_values in all_values[HEADER_ROW:]:
            asin = str(row_values[ASIN_COL]).strip() if len(row_values) > ASIN_COL else ""
            sku = str(row_values[SKU_COL]).strip() if len(row_values) > SKU_COL else ""
            fnsku = str(row_values[FNSKU_COL]).strip() if len(row_values) > FNSKU_COL else ""

            if not asin or asin in result:
                continue
            if sku or fnsku:
                result[asin] = {"sku": sku, "fnsku": fnsku}

        logger.info("売上/日シートからASIN→SKU/fnsku取得: %d件", len(result))
        return result
