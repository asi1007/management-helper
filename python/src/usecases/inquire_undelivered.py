from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime
from typing import Any

import click
import httpx

from domain.shipment.inquiry_message_builder import build_inquiry_message
from domain.shipment.undelivered_classifier import (
    DEFAULT_THRESHOLD_DAYS,
    InquiryVerdict,
    UndeliveredShipment,
    classify_shipment,
)
from infrastructure.amazon.auth import get_auth_token
from infrastructure.amazon.inbound_plan_creator import InboundPlanCreator
from infrastructure.spreadsheet.base_row import BaseRow
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet
from shared.config import AppConfig
from usecases.update_status_estimate import _extract_plan_identifier, _get_all_items

logger = logging.getLogger(__name__)

CHATWORK_MESSAGE_URL = "https://api.chatwork.com/v2/rooms/{room_id}/messages"
DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%m-%d", "%m/%d")
PRODUCT_NAME_MAX_CHARS = 30


def inquire_undelivered(
    config: AppConfig,
    repo: BaseSheetsRepository,
    *,
    threshold_days: int = DEFAULT_THRESHOLD_DAYS,
    send: bool = False,
    today: date | None = None,
) -> dict[str, Any]:
    reference_date = today or date.today()
    creator = InboundPlanCreator(get_auth_token(config.api_key, config.api_secret, config.refresh_token))
    sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)

    shipments = _collect_undelivered_shipments(sheet, creator, reference_date)
    verdicts = _classify_all(shipments, reference_date, threshold_days)
    _print_report(verdicts, reference_date)

    targets = verdicts[InquiryVerdict.NEEDS_INQUIRY]
    message = build_inquiry_message(targets, today=reference_date, to_account_id=config.chatwork_to_account_id)
    if message:
        click.echo("\n" + "=" * 50 + "\n[Chatwork問い合わせ文案]\n" + message + "\n" + "=" * 50)
    if send and message:
        _send_to_chatwork(config, message)
        click.echo("Chatworkへ送信しました")
    elif message:
        click.echo("送信するには --send を付けて再実行してください")

    return {"verdicts": verdicts, "message": message}


def _collect_undelivered_shipments(
    sheet: PurchaseSheet, creator: InboundPlanCreator, reference_date: date,
) -> list[UndeliveredShipment]:
    grouped: dict[str, list[BaseRow]] = defaultdict(list)
    identifiers: dict[str, dict[str, str]] = {}
    for row in sheet.all_data:
        if not _is_undelivered(row):
            continue
        identifier = _extract_plan_identifier(str(row.get("納品プラン") or ""))
        if not identifier:
            continue
        key = identifier.get("shipmentId") or identifier.get("inboundPlanId", "")
        grouped[key].append(row)
        identifiers[key] = identifier

    items_cache: dict[str, list[dict[str, Any]]] = {}
    return [
        _build_shipment(key, rows, identifiers[key], creator, items_cache)
        for key, rows in grouped.items()
    ]


def _is_undelivered(row: BaseRow) -> bool:
    has_shipped = bool(str(row.get("発送日") or "").strip())
    has_received = bool(str(row.get("受領日") or "").strip())
    has_plan = bool(str(row.get("納品プラン") or "").strip())
    return has_shipped and not has_received and has_plan


def _build_shipment(
    key: str,
    rows: list[BaseRow],
    identifier: dict[str, str],
    creator: InboundPlanCreator,
    items_cache: dict[str, list[dict[str, Any]]],
) -> UndeliveredShipment:
    shipment_id = identifier.get("shipmentId", "")
    inbound_plan_id = identifier.get("inboundPlanId", "")
    status = _fetch_status(creator, shipment_id)
    items = _get_all_items(creator, inbound_plan_id, shipment_id, items_cache)
    row_skus = {str(row.get("SKU") or "").strip() for row in rows}
    shipped, received = _sum_quantities(items, row_skus)
    return UndeliveredShipment(
        shipment_confirmation_id=shipment_id or inbound_plan_id,
        plan_alias=str(rows[0].get("プラン別名") or "").strip(),
        shipped_on=_parse_date(rows[0].get("発送日")),
        status=status,
        quantity_shipped=shipped or sum(int(row.get("購入数") or 0) for row in rows),
        quantity_received=received,
        tracking_number=str(rows[0].get("追跡番号") or "").strip(),
        product_names=_product_names(rows),
        rows=list(rows),
    )


def _product_names(rows: list[BaseRow]) -> list[str]:
    names: list[str] = []
    for row in rows:
        name = str(row.get("商品名") or "").strip()[:PRODUCT_NAME_MAX_CHARS]
        if name and name not in names:
            names.append(name)
    return names


def _fetch_status(creator: InboundPlanCreator, shipment_id: str) -> str:
    if not shipment_id:
        return ""
    try:
        return creator.get_shipment_status(shipment_id)
    except Exception as e:
        logger.warning("shipmentStatus取得失敗 (%s): %s", shipment_id, e)
        return ""


def _sum_quantities(items: list[dict[str, Any]], skus: set[str]) -> tuple[int, int]:
    shipped = 0
    received = 0
    for item in items:
        item_sku = str(item.get("SellerSKU", item.get("msku", item.get("sellerSku", "")))).strip()
        if item_sku in skus:
            shipped += int(item.get("QuantityShipped", item.get("quantityShipped", 0)))
            received += int(item.get("QuantityReceived", item.get("quantityReceived", 0)))
    return shipped, received


def _classify_all(
    shipments: list[UndeliveredShipment], reference_date: date, threshold_days: int,
) -> dict[InquiryVerdict, list[UndeliveredShipment]]:
    verdicts: dict[InquiryVerdict, list[UndeliveredShipment]] = {v: [] for v in InquiryVerdict}
    for shipment in shipments:
        verdict = classify_shipment(shipment, today=reference_date, threshold_days=threshold_days)
        verdicts[verdict].append(shipment)
    return verdicts


def _print_report(
    verdicts: dict[InquiryVerdict, list[UndeliveredShipment]], reference_date: date,
) -> None:
    for verdict, shipments in verdicts.items():
        if not shipments:
            continue
        click.echo(f"\n[{verdict.value}] {len(shipments)}件")
        for shipment in sorted(shipments, key=lambda s: s.elapsed_days(reference_date) or 0, reverse=True):
            elapsed = shipment.elapsed_days(reference_date)
            elapsed_text = f"{elapsed}日経過" if elapsed is not None else "発送日不明"
            click.echo(
                f"  {shipment.shipment_confirmation_id} | {shipment.plan_alias} | {elapsed_text} | "
                f"{len(shipment.rows)}行 | 発送{shipment.quantity_shipped}/受領{shipment.quantity_received}"
            )
    if verdicts[InquiryVerdict.ALREADY_RECEIVED]:
        click.echo("\n※ 受領済みの分は update-status を実行するとシートの受領日が埋まります")


def _send_to_chatwork(config: AppConfig, message: str) -> None:
    if not (config.chatwork_api_token and config.chatwork_room_id):
        raise RuntimeError("Chatworkの認証情報が設定されていません")
    response = httpx.post(
        CHATWORK_MESSAGE_URL.format(room_id=config.chatwork_room_id),
        headers={"X-ChatWorkToken": config.chatwork_api_token},
        data={"body": message},
        timeout=30.0,
    )
    response.raise_for_status()


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()[:10]
    if not text:
        return None
    for fmt in DATE_FORMATS:
        try:
            parsed = datetime.strptime(text, fmt).date()
        except ValueError:
            continue
        return parsed.replace(year=date.today().year) if parsed.year == 1900 else parsed
    return None
