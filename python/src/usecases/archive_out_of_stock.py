from __future__ import annotations

import logging

from shared.config import AppConfig
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet

logger = logging.getLogger(__name__)

ARCHIVE_SHEET_NAME = "過去仕入れログ"
STATUS_COL = "状態"
OUT_OF_STOCK = "在庫なし"
FIRST_DATA_ROW = 6


def archive_out_of_stock(config: AppConfig, repo: BaseSheetsRepository) -> None:
    sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    archive_sheet = repo.open_spreadsheet(config.sheet_id).worksheet(ARCHIVE_SHEET_NAME)

    rows_to_archive = [
        row
        for row in sheet.all_data
        if row.row_number >= FIRST_DATA_ROW
        and str(row.get(STATUS_COL) or "").strip() == OUT_OF_STOCK
    ]
    if not rows_to_archive:
        logger.info("在庫なし行なし")
        return

    archive_sheet.append_rows(
        [list(row) for row in rows_to_archive],
        value_input_option="USER_ENTERED",
    )
    _delete_rows_in_batch(sheet._worksheet, [row.row_number for row in rows_to_archive])
    logger.info("在庫なし%d行を過去仕入れログへ移動しました", len(rows_to_archive))


def _delete_rows_in_batch(worksheet: object, row_numbers: list[int]) -> None:
    requests = [
        {
            "deleteDimension": {
                "range": {
                    "sheetId": worksheet.id,
                    "dimension": "ROWS",
                    "startIndex": row_num - 1,
                    "endIndex": row_num,
                }
            }
        }
        for row_num in sorted(row_numbers, reverse=True)
    ]
    worksheet.spreadsheet.batch_update({"requests": requests})
