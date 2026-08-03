from __future__ import annotations

import logging
from typing import Any

from shared.config import AppConfig
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet

logger = logging.getLogger(__name__)

FORMULA_COLUMNS = ("状態",)


def delete_blank_rows(config: AppConfig, repo: BaseSheetsRepository, *, dry_run: bool = True) -> list[int]:
    sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    blank_rows = _find_blank_rows(sheet)
    if not blank_rows:
        logger.info("空白行はありません")
        return []
    logger.info("空白行を検出: %s (%d行)", blank_rows, len(blank_rows))
    if dry_run:
        logger.info("dry-run のため削除しません")
        return blank_rows
    worksheet = sheet._worksheet
    worksheet.spreadsheet.batch_update(
        {"requests": _build_delete_requests(worksheet.id, blank_rows)}
    )
    logger.info("空白行%d件を削除しました", len(blank_rows))
    return blank_rows


def _find_blank_rows(sheet: PurchaseSheet) -> list[int]:
    return [row.row_number for row in sheet.all_data if _is_blank_row(sheet._headers, list(row))]


def _is_blank_row(headers: list[str], values: list[Any]) -> bool:
    for index, value in enumerate(values):
        header = headers[index] if index < len(headers) else ""
        if header in FORMULA_COLUMNS:
            continue
        if str(value).strip():
            return False
    return True


def _build_delete_requests(sheet_id: int, row_numbers: list[int]) -> list[dict[str, Any]]:
    return [
        {
            "deleteDimension": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": row_number - 1,
                    "endIndex": row_number,
                }
            }
        }
        for row_number in sorted(row_numbers, reverse=True)
    ]
