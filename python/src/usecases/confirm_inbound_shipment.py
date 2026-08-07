from __future__ import annotations

import logging
from datetime import date
from typing import Any

import click

from domain.shipment.delivery_window_selector import select_delivery_window_option_id
from infrastructure.amazon.auth import get_auth_token
from infrastructure.amazon.inbound_plan_creator import InboundPlanCreator
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet
from shared.config import AppConfig
from usecases.set_packing_info import (
    build_packing_body,
    extract_inbound_plan_id,
    parse_carton_input,
)

logger = logging.getLogger(__name__)

OWN_CARRIER_SOLUTION = "USE_YOUR_OWN_CARRIER"
SMALL_PARCEL_MODE = "GROUND_SMALL_PARCEL"
OTHER_CARRIER_NAME = "Other"


def confirm_inbound_shipment(
    config: AppConfig,
    repo: BaseSheetsRepository,
    row_numbers: list[int],
    *,
    carton_text: str,
    ship_date: date,
    lead_days: int | None = None,
) -> dict[str, Any]:
    cartons = parse_carton_input(carton_text)
    if not cartons:
        raise RuntimeError("箱情報がパースできません")

    sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    sheet.get_rows_by_numbers(row_numbers)
    inbound_plan_id = _resolve_inbound_plan_id(sheet)
    creator = InboundPlanCreator(get_auth_token(config.api_key, config.api_secret, config.refresh_token))

    _apply_packing(creator, inbound_plan_id, cartons)
    placement_option_id, shipment_id = _apply_placement(creator, inbound_plan_id)
    _apply_delivery_window(creator, inbound_plan_id, shipment_id, ship_date, lead_days)
    _apply_transportation(creator, inbound_plan_id, placement_option_id, shipment_id, ship_date)
    _write_box_count(sheet, cartons)

    shipment = creator.get_shipment(inbound_plan_id, shipment_id)
    return {
        "inboundPlanId": inbound_plan_id,
        "shipmentId": shipment_id,
        "shipmentConfirmationId": shipment.get("shipmentConfirmationId", ""),
        "destination": (shipment.get("destination") or {}).get("warehouseId", ""),
        "deliveryWindow": shipment.get("selectedDeliveryWindow") or {},
    }


def _resolve_inbound_plan_id(sheet: PurchaseSheet) -> str:
    plan_cell = str(sheet.data[0].get("納品プラン") or "").strip() if sheet.data else ""
    inbound_plan_id = extract_inbound_plan_id(plan_cell)
    if not inbound_plan_id:
        raise RuntimeError("納品プランIDが取得できません")
    click.echo(f"納品プランID: {inbound_plan_id}")
    return inbound_plan_id


def _apply_packing(creator: InboundPlanCreator, inbound_plan_id: str, cartons: list[dict[str, Any]]) -> None:
    options = creator.list_packing_options(inbound_plan_id)
    if not options:
        raise RuntimeError("packingOptionが見つかりません")
    creator.confirm_packing_option(inbound_plan_id, str(options[0]["packingOptionId"]))

    packing_group_id = creator.get_packing_group_id(inbound_plan_id)
    items = creator.get_packing_group_items(inbound_plan_id, packing_group_id)
    creator.set_packing_information(inbound_plan_id, build_packing_body(packing_group_id, cartons, items))
    click.echo(f"梱包情報を登録: {len(cartons)}種類の輸送箱")


def _apply_placement(creator: InboundPlanCreator, inbound_plan_id: str) -> tuple[str, str]:
    creator.get_placement_options(inbound_plan_id)
    options = creator.list_placement_options(inbound_plan_id)
    if not options:
        raise RuntimeError("placementOptionが見つかりません")
    selected = min(options, key=_placement_fee_total)
    shipment_ids = list(selected.get("shipmentIds", []))
    if len(shipment_ids) != 1:
        raise RuntimeError(f"shipmentが1件ではありません: {shipment_ids}")
    creator.confirm_placement_option(inbound_plan_id, str(selected["placementOptionId"]))
    click.echo(f"配送先を確定: 手数料 {_placement_fee_total(selected)}円")
    return str(selected["placementOptionId"]), shipment_ids[0]


def _apply_delivery_window(
    creator: InboundPlanCreator,
    inbound_plan_id: str,
    shipment_id: str,
    ship_date: date,
    lead_days: int | None,
) -> None:
    creator.generate_delivery_window_options(inbound_plan_id, shipment_id)
    options = creator.list_delivery_window_options(inbound_plan_id, shipment_id)
    option_id = select_delivery_window_option_id(options, ship_date=ship_date, lead_days=lead_days)
    creator.confirm_delivery_window_option(inbound_plan_id, shipment_id, option_id)
    click.echo(f"配送ウィンドウを確定: {_window_label(options, option_id)}")


def _apply_transportation(
    creator: InboundPlanCreator,
    inbound_plan_id: str,
    placement_option_id: str,
    shipment_id: str,
    ship_date: date,
) -> None:
    creator.generate_transportation_options(
        inbound_plan_id, placement_option_id, shipment_id, ship_date.strftime("%Y-%m-%d"),
    )
    options = creator.list_transportation_options(inbound_plan_id, shipment_id)
    selected = _find_other_carrier_option(options)
    creator.confirm_transportation_option(inbound_plan_id, shipment_id, str(selected["transportationOptionId"]))
    click.echo(f"配送業者を確定: その他（Amazonパートナーキャリア以外） 出荷日 {ship_date:%Y/%m/%d}")


def _find_other_carrier_option(options: list[dict[str, Any]]) -> dict[str, Any]:
    for option in options:
        carrier_name = (option.get("carrier") or {}).get("name", "")
        if (
            option.get("shippingSolution") == OWN_CARRIER_SOLUTION
            and option.get("shippingMode") == SMALL_PARCEL_MODE
            and carrier_name == OTHER_CARRIER_NAME
        ):
            return option
    raise RuntimeError("配送業者「その他」の配送オプションが見つかりません")


def _placement_fee_total(option: dict[str, Any]) -> float:
    return sum(float((fee.get("value") or {}).get("amount", 0)) for fee in option.get("fees", []))


def _window_label(options: list[dict[str, Any]], option_id: str) -> str:
    for option in options:
        if option.get("deliveryWindowOptionId") == option_id:
            return f"{str(option.get('startDate'))[:10]} 〜 {str(option.get('endDate'))[:10]}"
    return option_id


def _write_box_count(sheet: PurchaseSheet, cartons: list[dict[str, Any]]) -> None:
    box_count = sum(int(carton["count"]) for carton in cartons)
    sheet.write_column_by_func("段ボール箱数", lambda _row, _index: box_count)
