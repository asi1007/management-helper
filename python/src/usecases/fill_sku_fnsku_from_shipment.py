from __future__ import annotations

import logging
import re

import gspread

from shared.config import AppConfig
from infrastructure.amazon.auth import get_auth_token
from infrastructure.amazon.inbound_plan_creator import InboundPlanCreator
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet

logger = logging.getLogger(__name__)

ASIN_COL = "ASIN"
SKU_COL = "SKU"
FNSKU_COL = "FNSKU"
PLAN_COL = "納品プラン"


def fill_sku_fnsku_from_shipment(config: AppConfig, repo: BaseSheetsRepository) -> None:
    creator = InboundPlanCreator(
        get_auth_token(config.api_key, config.api_secret, config.refresh_token)
    )
    sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    sku_col = sheet._get_column_index_by_name(SKU_COL) + 1
    fnsku_col = sheet._get_column_index_by_name(FNSKU_COL) + 1
    asin_map = _build_asin_map(sheet)
    pairs_cache: dict[str, list[tuple[str, str]]] = {}

    updates: list[dict] = []
    for row in sheet.all_data:
        cur_sku = str(row.get(SKU_COL) or "").strip()
        cur_fnsku = str(row.get(FNSKU_COL) or "").strip()
        if cur_sku and cur_fnsku:
            continue
        shipment_id = _extract_shipment_id(str(row.get(PLAN_COL) or ""))
        if not shipment_id:
            continue
        pairs = _get_pairs(creator, shipment_id, pairs_cache)
        asin = str(row.get(ASIN_COL) or "").strip()
        new_sku, new_fnsku = _resolve_sku_fnsku(cur_sku, cur_fnsku, pairs, asin, asin_map)
        if new_sku and not cur_sku:
            updates.append({"range": gspread.utils.rowcol_to_a1(row.row_number, sku_col), "values": [[new_sku]]})
        if new_fnsku and not cur_fnsku:
            updates.append({"range": gspread.utils.rowcol_to_a1(row.row_number, fnsku_col), "values": [[new_fnsku]]})

    if updates:
        sheet._worksheet.batch_update(updates, value_input_option="USER_ENTERED")
    logger.info("SKU/FNSKU補完: %d セル書き込み", len(updates))


def _extract_shipment_id(cell_value: str) -> str:
    m = re.search(r"(FBA[A-Z0-9]{9})", cell_value)
    return m.group(1) if m else ""


def _build_asin_map(sheet: PurchaseSheet) -> dict[str, tuple[str, str]]:
    result: dict[str, tuple[str, str]] = {}
    for row in sheet.all_data:
        asin = str(row.get(ASIN_COL) or "").strip()
        sku = str(row.get(SKU_COL) or "").strip()
        fnsku = str(row.get(FNSKU_COL) or "").strip()
        if asin and sku and asin not in result:
            result[asin] = (sku, fnsku)
    return result


def _get_pairs(
    creator: InboundPlanCreator, shipment_id: str, cache: dict[str, list[tuple[str, str]]]
) -> list[tuple[str, str]]:
    if shipment_id in cache:
        return cache[shipment_id]
    pairs: list[tuple[str, str]] = []
    try:
        for item in creator.get_shipment_items(shipment_id):
            sku = str(item.get("SellerSKU", item.get("msku", item.get("sellerSku", "")))).strip()
            fnsku = str(item.get("FulfillmentNetworkSKU", item.get("fulfillmentNetworkSku", ""))).strip()
            if sku:
                pairs.append((sku, fnsku))
    except Exception as e:
        logger.warning("shipment items取得失敗 (%s): %s", shipment_id, e)
    cache[shipment_id] = pairs
    return pairs


def _resolve_sku_fnsku(
    cur_sku: str,
    cur_fnsku: str,
    pairs: list[tuple[str, str]],
    asin: str,
    asin_map: dict[str, tuple[str, str]],
) -> tuple[str | None, str | None]:
    if cur_sku and not cur_fnsku:
        for sku, fnsku in pairs:
            if sku == cur_sku:
                return None, (fnsku or None)
        return None, None
    if cur_fnsku and not cur_sku:
        for sku, fnsku in pairs:
            if fnsku == cur_fnsku:
                return (sku or None), None
        return None, None
    if not cur_sku and not cur_fnsku:
        if len(pairs) == 1:
            sku, fnsku = pairs[0]
            return (sku or None), (fnsku or None)
        candidate = asin_map.get(asin)
        if candidate and any(candidate[0] == sku for sku, _ in pairs):
            return candidate[0] or None, candidate[1] or None
        return None, None
    return None, None
