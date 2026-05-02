from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

from shared.config import AppConfig
from infrastructure.amazon.auth import get_auth_token
from infrastructure.amazon.inbound_plan_creator import InboundPlanCreator
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet

logger = logging.getLogger(__name__)

INVENTORY_COL = "在庫数"
RECEIVED_DATE_COL = "受領日"
TARGET_STATUSES = ["納品中", "自宅発送"]


def update_status_estimate(config: AppConfig, repo: BaseSheetsRepository) -> None:
    access_token = get_auth_token(config.api_key, config.api_secret, config.refresh_token)
    creator = InboundPlanCreator(access_token)
    sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    sheet.filter("状態", TARGET_STATUSES)
    if not sheet.data:
        logger.info("対象行(%s)がありません", "/".join(TARGET_STATUSES))
        return
    status_cache: dict[str, str] = {}
    items_cache: dict[str, list[dict[str, Any]]] = {}
    for row in sheet.data:
        plan_cell = str(row.get("納品プラン") or "").strip()
        sku = str(row.get("SKU") or "").strip()
        purchase_qty = int(row.get("購入数") or 0)
        identifier = _extract_plan_identifier(plan_cell)
        if not identifier:
            continue
        shipment_id = identifier.get("shipmentId", "")
        inbound_plan_id = identifier.get("inboundPlanId", "")
        if shipment_id and shipment_id not in status_cache:
            try:
                status_cache[shipment_id] = creator.get_shipment_status(shipment_id)
            except Exception as e:
                logger.warning("shipmentStatus取得失敗 (%s): %s", shipment_id, e)
                continue
        status = status_cache.get(shipment_id, "")
        is_closed = status == "CLOSED"
        all_items = _get_all_items(creator, inbound_plan_id, shipment_id, items_cache)
        qty_shipped, qty_received = _sum_quantities_for_sku(all_items, sku)
        is_received = False
        if is_closed:
            is_received = True
        elif qty_shipped > 0 and qty_received > 0:
            diff_ratio = abs(qty_shipped - qty_received) / qty_shipped
            is_received = diff_ratio <= 0.1
        if is_received:
            row_num = row.row_number
            inv_col = sheet._get_column_index_by_name(INVENTORY_COL) + 1
            received_qty = qty_received if qty_received > 0 else purchase_qty
            sheet.write_cell(row_num, inv_col, received_qty)
            try:
                date_col = sheet._get_column_index_by_name(RECEIVED_DATE_COL) + 1
                sheet.write_cell(row_num, date_col, datetime.now().strftime("%Y/%m/%d"))
            except ValueError:
                pass
            logger.info("行%d: 納品済み (status=%s, shipped=%d, received=%d)", row_num, status, qty_shipped, qty_received)
        else:
            logger.info("行%d: まだ納品中 (status=%s, shipped=%d, received=%d)", row.row_number, status, qty_shipped, qty_received)


def _extract_plan_identifier(cell_value: str) -> dict[str, str] | None:
    hyperlink_match = re.search(r'HYPERLINK\("([^"]+)"', cell_value)
    url = hyperlink_match.group(1) if hyperlink_match else cell_value
    result: dict[str, str] = {}
    wf_match = re.search(r"wf=(wf[a-zA-Z0-9]+)", url)
    if wf_match:
        result["inboundPlanId"] = wf_match.group(1)
    fba_match = re.search(r"(FBA[A-Z0-9]+)", url)
    if fba_match:
        result["shipmentId"] = fba_match.group(1)
    return result if result else None


def _get_all_items(
    creator: InboundPlanCreator, inbound_plan_id: str, shipment_id: str,
    cache: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    cache_key = inbound_plan_id or shipment_id
    if cache_key in cache:
        return cache[cache_key]
    items: list[dict[str, Any]] = []
    if inbound_plan_id:
        try:
            shipments = creator.list_shipments(inbound_plan_id)
            for s in shipments:
                sid = s.get("shipmentId", "")
                if sid:
                    items.extend(creator.get_shipment_items(sid))
        except Exception:
            pass
    if not items and shipment_id:
        try:
            items = creator.get_shipment_items(shipment_id)
        except Exception:
            pass
    cache[cache_key] = items
    return items


def _sum_quantities_for_sku(items: list[dict[str, Any]], sku: str) -> tuple[int, int]:
    shipped = 0
    received = 0
    for item in items:
        item_sku = item.get("SellerSKU", item.get("msku", item.get("sellerSku", "")))
        if str(item_sku).strip() == sku:
            shipped += int(item.get("QuantityShipped", item.get("quantityShipped", 0)))
            received += int(item.get("QuantityReceived", item.get("quantityReceived", 0)))
    return shipped, received
