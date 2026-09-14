from __future__ import annotations

import logging
from datetime import date

import gspread

from shared.config import AppConfig
from domain.inventory.value_objects.stock_shortfall import collect_shortfalls
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet
from infrastructure.todoist.stock_shortfall_notifier import StockShortfallNotifier

logger = logging.getLogger(__name__)

INVENTORY_COL = "在庫数"
PURCHASE_COL = "購入数"
# 受領が始まった日。空でなく在庫数が空なら、FCは受領中でシートはまだ受け皿を持たない
RECEIVING_STARTED_COL = "受領開始日"
STOCK_SHEET_NAME = "stock"
# FC内にあって、これから売れる数量。
#   受領中を外すと納品を受領した直後に在庫0と誤判定する。
#   転送中・処理中はFC内にあるので数える。
#   注文確保は客の注文が付いていて出荷されるので数えない。
#   予約済合計(=注文確保+転送中+処理中)は二重計上になるので使わない。
STOCK_QUANTITY_COLUMNS = ("販売可能", "受領中", "転送中", "処理中")


class StockUnavailableError(RuntimeError):
    pass


def update_inventory_estimate(
    config: AppConfig, repo: BaseSheetsRepository, notifier: object | None = None
) -> None:
    notifier = notifier or StockShortfallNotifier(
        api_token=getattr(config, "todoist_api_token", ""),
        project=getattr(config, "todoist_project", "INBOX"),
    )
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
    skipped: list[str] = []
    assigned: dict[str, int] = {}
    for asin, rows in asin_groups.items():
        # stockに無い = 在庫が0ではなく「情報が無い」。0を書くと在庫なし扱いで行が消える。
        if asin not in asin_to_stock:
            skipped.append(asin)
            continue
        available = asin_to_stock[asin]
        remaining = available
        assigned[asin] = 0
        for row in reversed(rows):
            purchase_qty = _parse_quantity(row.get(PURCHASE_COL))
            estimated = min(purchase_qty, remaining)
            remaining = max(0, remaining - estimated)
            assigned[asin] += estimated
            existing = _parse_quantity(row.get(INVENTORY_COL))
            if estimated != existing:
                cell = gspread.utils.rowcol_to_a1(row.row_number, inv_col)
                updates.append({"range": cell, "values": [[estimated]]})
            logger.info("行%d: ASIN=%s, 在庫推測=%d (既存=%d)", row.row_number, asin, estimated, existing)
    if skipped:
        logger.warning("stockに無いため在庫数を更新しなかったASIN: %s", ", ".join(skipped))
    if updates:
        sheet._worksheet.batch_update(updates, value_input_option="USER_ENTERED")
    logger.info("在庫数更新完了: written=%d, asins=%d", len(updates), len(asin_groups))
    # FBAにあるのに行へ収まらない在庫は、受け皿の行が消えた合図。放置すると気づけない
    capacity = _merge_capacity(assigned, _sum_receiving_quantity(sheet))
    shortfalls = collect_shortfalls(asin_to_stock, capacity)
    if shortfalls:
        logger.warning(
            "FBA在庫が行に収まっていません: %d件 %d個",
            len(shortfalls),
            sum(s.quantity for s in shortfalls),
        )
    notifier.notify(shortfalls, date.today().isoformat())


def _sum_receiving_quantity(sheet: PurchaseSheet) -> dict[str, int]:
    # 在庫数が入るのは受領率90%を超えてから。それまでFCが受領した分は
    # FBA在庫には載るのに配分先が無く、未割当として毎回通知されていた。
    if _column_index_or_none(sheet, RECEIVING_STARTED_COL) is None:
        logger.warning(
            "%s列がないため受領中の行を受け皿に数えません", RECEIVING_STARTED_COL
        )
        return {}
    result: dict[str, int] = {}
    for row in sheet.all_data:
        asin = _cell(row, "ASIN")
        if not asin or not _cell(row, RECEIVING_STARTED_COL):
            continue
        if _cell(row, INVENTORY_COL):
            continue
        result[asin] = result.get(asin, 0) + _parse_quantity(row.get(PURCHASE_COL))
    return result


def _merge_capacity(assigned: dict[str, int], receiving: dict[str, int]) -> dict[str, int]:
    return {
        asin: assigned.get(asin, 0) + receiving.get(asin, 0)
        for asin in set(assigned) | set(receiving)
    }


def _column_index_or_none(sheet: PurchaseSheet, column_name: str) -> int | None:
    try:
        return sheet._get_column_index_by_name(column_name)
    except ValueError:
        return None


def _cell(row: object, column_name: str) -> str:
    try:
        return str(row.get(column_name) or "").strip()
    except (IndexError, ValueError):
        return ""


def _load_asin_to_available_stock(repo: BaseSheetsRepository, sheet_id: str) -> dict[str, int]:
    try:
        spreadsheet = repo.open_spreadsheet(sheet_id)
        stock_sheet = spreadsheet.worksheet(STOCK_SHEET_NAME)
    except Exception as exc:
        raise StockUnavailableError(f"{STOCK_SHEET_NAME}シートを開けません: {exc}") from exc
    all_values = stock_sheet.get_all_values()
    if not all_values:
        raise StockUnavailableError(f"{STOCK_SHEET_NAME}シートが空です")
    headers = [str(h).strip() for h in all_values[0]]
    asin_col = next((i for i, h in enumerate(headers) if h.lower() == "asin"), None)
    quantity_cols = [
        next((i for i, h in enumerate(headers) if keyword in h), None)
        for keyword in STOCK_QUANTITY_COLUMNS
    ]
    if asin_col is None or any(col is None for col in quantity_cols):
        raise StockUnavailableError(
            f"{STOCK_SHEET_NAME}シートにASINまたは{'・'.join(STOCK_QUANTITY_COLUMNS)}列が"
            f"ありません: headers={headers}"
        )
    last_col = max([asin_col, *quantity_cols])
    result: dict[str, int] = {}
    for row_values in all_values[1:]:
        if len(row_values) <= last_col:
            continue
        asin = str(row_values[asin_col]).strip()
        stock = sum(_parse_quantity(row_values[col]) for col in quantity_cols)
        if asin:
            result[asin] = result.get(asin, 0) + stock
    if not result:
        raise StockUnavailableError(f"{STOCK_SHEET_NAME}シートからASINを1件も読み取れません")
    if not any(result.values()):
        raise StockUnavailableError(
            f"{STOCK_SHEET_NAME}シートの在庫が全{len(result)}ASINで0です。"
            "IMPORTRANGEの読み込み失敗が疑われるため中断しました"
        )
    return result


def _parse_quantity(value: object) -> int:
    if value is None:
        return 0
    text = str(value).replace(",", "").strip()
    if not text:
        return 0
    try:
        return int(text)
    except (ValueError, TypeError):
        return 0
