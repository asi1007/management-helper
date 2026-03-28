from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import gspread

from infrastructure.spreadsheet.base_sheet import BaseSheet
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository

logger = logging.getLogger(__name__)


class WorkRecordSheet(BaseSheet):
    def __init__(self, repo: BaseSheetsRepository, sheet_id: str, sheet_name: str) -> None:
        super().__init__(repo=repo, sheet_id=sheet_id, sheet_name=sheet_name, header_row=1)

    def append_record(
        self,
        asin: str,
        purchase_date: str,
        status: str,
        timestamp: str,
        quantity: int | None = None,
        reason: str | None = None,
        comment: str | None = None,
        order_number: str | None = None,
    ) -> None:
        a_col_values = self._worksheet.col_values(1)
        last_a = len(a_col_values) if a_col_values else 0
        new_row = max(2, last_a + 1)
        cells: list[tuple[int, int, Any]] = [
            (new_row, 1, asin),
            (new_row, 2, purchase_date),
            (new_row, 3, status),
            (new_row, 4, timestamp),
        ]
        if quantity is not None:
            cells.append((new_row, 5, quantity))
        if reason is not None:
            cells.append((new_row, 6, reason))
        if comment:
            cells.append((new_row, 7, comment))
        if order_number:
            cells.append((new_row, 8, order_number))
        for r, c, v in cells:
            self._worksheet.update_cell(r, c, v)
        logger.info("作業記録を追加: ASIN=%s, ステータス=%s, 時刻=%s", asin, status, timestamp)

    def append_inbound_plan_summary(
        self,
        plan_result: dict[str, Any],
        asin_records: list[dict[str, Any]],
    ) -> None:
        if not asin_records:
            return
        inbound_plan_id = str(plan_result.get("inboundPlanId", "")).strip()
        link = str(plan_result.get("link", "")).strip()
        l_col_values = self._worksheet.col_values(12)
        last_l = len(l_col_values) if l_col_values else 0
        new_row = max(2, last_l + 1)
        today = datetime.now().strftime("%Y/%m/%d")
        for r in asin_records:
            asin = str(r.get("asin", "")).strip()
            qty = int(r.get("quantity", 0))
            order_no = str(r.get("orderNumber", "")).strip()
            if not asin or qty <= 0:
                continue
            self._worksheet.update_cell(new_row, 11, today)
            if link:
                text = inbound_plan_id or "納品プラン"
                cell_label = gspread.utils.rowcol_to_a1(new_row, 12)
                self._worksheet.update_acell(cell_label, f'=HYPERLINK("{link}", "{text}")')
            else:
                self._worksheet.update_cell(new_row, 12, inbound_plan_id)
            self._worksheet.update_cell(new_row, 13, asin)
            self._worksheet.update_cell(new_row, 14, qty)
            if order_no:
                self._worksheet.update_cell(new_row, 15, order_no)
            new_row += 1
