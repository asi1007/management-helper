from __future__ import annotations

import logging

from shared.config import AppConfig
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet

logger = logging.getLogger(__name__)

STATUS_COL = "ステータス推測値"
INVENTORY_COL = "在庫数推測値"


def update_inventory_estimate(config: AppConfig, repo: BaseSheetsRepository) -> None:
    asin_to_stock = _load_asin_to_available_stock(repo, config.sheet_id)
    sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    sheet.filter("状態", ["在庫あり", "在庫なし"])
    if not sheet.data:
        logger.info("対象行がありません")
        return
    asin_groups: dict[str, list] = {}
    for row in sheet.data:
        asin = str(row.get("ASIN") or "").strip()
        if asin:
            asin_groups.setdefault(asin, []).append(row)
    status_col = sheet._get_column_index_by_name(STATUS_COL) + 1
    inv_col = sheet._get_column_index_by_name(INVENTORY_COL) + 1
    for asin, rows in asin_groups.items():
        available = asin_to_stock.get(asin, 0)
        remaining = available
        for row in reversed(rows):
            purchase_qty = int(row.get("購入数") or 0)
            estimated = min(purchase_qty, remaining)
            remaining = max(0, remaining - estimated)
            sheet.write_cell(row.row_number, inv_col, estimated)
            new_status = "在庫なし" if estimated == 0 else "在庫あり"
            sheet.write_cell(row.row_number, status_col, new_status)
            logger.info("行%d: ASIN=%s, 在庫推測=%d, ステータス=%s", row.row_number, asin, estimated, new_status)


def _load_asin_to_available_stock(repo: BaseSheetsRepository, sheet_id: str) -> dict[str, int]:
    try:
        spreadsheet = repo.open_spreadsheet(sheet_id)
        stock_sheet = spreadsheet.worksheet("stock")
    except Exception:
        logger.warning("stockシートが見つかりません")
        return {}
    all_values = stock_sheet.get_all_values()
    if not all_values:
        return {}
    headers = [str(h).strip() for h in all_values[0]]
    asin_col = headers.index("ASIN") if "ASIN" in headers else None
    available_col = headers.index("販売可能") if "販売可能" in headers else None
    if asin_col is None or available_col is None:
        logger.warning("stockシートにASINまたは販売可能列がありません")
        return {}
    result: dict[str, int] = {}
    for row_values in all_values[1:]:
        if len(row_values) <= max(asin_col, available_col):
            continue
        asin = str(row_values[asin_col]).strip()
        try:
            stock = int(row_values[available_col])
        except (ValueError, TypeError):
            stock = 0
        if asin:
            result[asin] = result.get(asin, 0) + stock
    return result
