from __future__ import annotations

import logging
from datetime import date, timedelta

import gspread

from shared.config import AppConfig
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet

logger = logging.getLogger(__name__)

ARCHIVE_SHEET_NAME = "過去仕入れログ"
STATUS_COL = "状態"
RECEIVED_COL = "受領日"
OUT_OF_STOCK = "在庫なし"
FIRST_DATA_ROW = 6
MAX_ARCHIVE_ROWS = 20
SHEETS_EPOCH = date(1899, 12, 30)


class TooManyArchiveRowsError(RuntimeError):
    pass


def archive_out_of_stock(
    config: AppConfig, repo: BaseSheetsRepository, *, today: date | None = None
) -> None:
    cutoff = _previous_month_end(today or date.today())
    sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    archive_sheet = repo.open_spreadsheet(config.sheet_id).worksheet(ARCHIVE_SHEET_NAME)

    received_dates = _read_received_dates(sheet)
    rows_to_archive = [
        row
        for row in sheet.all_data
        if row.row_number >= FIRST_DATA_ROW
        and str(row.get(STATUS_COL) or "").strip() == OUT_OF_STOCK
        and _received_on_or_before(received_dates.get(row.row_number), cutoff)
    ]
    if not rows_to_archive:
        logger.info("%s以前に受領した在庫なし行なし", cutoff.isoformat())
        return
    if len(rows_to_archive) > MAX_ARCHIVE_ROWS:
        raise TooManyArchiveRowsError(
            f"在庫なしが{len(rows_to_archive)}行あり上限{MAX_ARCHIVE_ROWS}行を超えるため中断しました。"
            "在庫数の一括ゼロ化が起きていないか確認してください"
        )

    archive_sheet.append_rows(
        [list(row) for row in rows_to_archive],
        value_input_option="USER_ENTERED",
    )
    _delete_rows_in_batch(sheet._worksheet, [row.row_number for row in rows_to_archive])
    logger.info(
        "%s以前に受領した在庫なし%d行を過去仕入れログへ移動しました",
        cutoff.isoformat(),
        len(rows_to_archive),
    )


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


def _previous_month_end(today: date) -> date:
    return today.replace(day=1) - timedelta(days=1)


def _received_on_or_before(received: date | None, cutoff: date) -> bool:
    return received is not None and received <= cutoff


def _read_received_dates(sheet: PurchaseSheet) -> dict[int, date | None]:
    column_number = sheet._get_column_index_by_name(RECEIVED_COL) + 1
    letter = gspread.utils.rowcol_to_a1(1, column_number)[:-1]
    cells = sheet._worksheet.get_values(
        f"{letter}{sheet.start_row}:{letter}",
        value_render_option="UNFORMATTED_VALUE",
    )
    return {
        sheet.start_row + offset: _to_date(cell[0] if cell else "")
        for offset, cell in enumerate(cells)
    }


def _to_date(value: object) -> date | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return SHEETS_EPOCH + timedelta(days=int(value))
