from __future__ import annotations

import logging

import gspread

from shared.config import AppConfig
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet

logger = logging.getLogger(__name__)

INVENTORY_COL = "在庫数"


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
    inv_col = sheet._get_column_index_by_name(INVENTORY_COL) + 1
    updates: list[dict] = []
    for asin, rows in asin_groups.items():
        available = asin_to_stock.get(asin, 0)
        remaining = available
        for row in reversed(rows):
            purchase_qty = int(row.get("購入数") or 0)
            estimated = min(purchase_qty, remaining)
            remaining = max(0, remaining - estimated)
            existing = int(row.get(INVENTORY_COL) or 0)
            if estimated != existing:
                cell = gspread.utils.rowcol_to_a1(row.row_number, inv_col)
                updates.append({"range": cell, "values": [[estimated]]})
            logger.info("行%d: ASIN=%s, 在庫推測=%d (既存=%d)", row.row_number, asin, estimated, existing)
    if updates:
        sheet._worksheet.batch_update(updates, value_input_option="USER_ENTERED")
    logger.info("在庫数更新完了: written=%d, asins=%d", len(updates), len(asin_groups))


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
    asin_col = next((i for i, h in enumerate(headers) if h.lower() == "asin"), None)
    available_col = next((i for i, h in enumerate(headers) if "販売可能" in h), None)
    if asin_col is None or available_col is None:
        logger.warning("stockシートにASINまたは販売可能列がありません: headers=%s", headers)
        return {}
    result: dict[str, int] = {}
    for row_values in all_values[1:]:
        if len(row_values) <= max(asin_col, available_col):
            continue
        asin = str(row_values[asin_col]).strip()
        stock = _parse_stock_quantity(row_values[available_col])
        if asin:
            result[asin] = result.get(asin, 0) + stock
    return result


def _parse_stock_quantity(value: object) -> int:
    if value is None:
        return 0
    text = str(value).replace(",", "").strip()
    if not text:
        return 0
    try:
        return int(text)
    except (ValueError, TypeError):
        return 0
