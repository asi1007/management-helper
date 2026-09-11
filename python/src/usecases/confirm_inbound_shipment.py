from __future__ import annotations

import logging
import re
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
    is_full_inbound_plan_id,
    parse_carton_input,
)

logger = logging.getLogger(__name__)

OWN_CARRIER_SOLUTION = "USE_YOUR_OWN_CARRIER"
SMALL_PARCEL_MODE = "GROUND_SMALL_PARCEL"
OTHER_CARRIER_NAME = "Other"
SHIPMENT_ID_PATTERN = re.compile(r"FBA[A-Z0-9]{9}")
SHIPMENT_SUMMARY_URL = "https://sellercentral.amazon.co.jp/fba/inbound-shipment/summary/"


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
    creator = InboundPlanCreator(get_auth_token())

    _apply_packing(creator, inbound_plan_id, cartons)
    placement_option_id, shipment_id = _apply_placement(creator, inbound_plan_id)
    _apply_delivery_window(creator, inbound_plan_id, shipment_id, ship_date, lead_days)
    _apply_transportation(creator, inbound_plan_id, placement_option_id, shipment_id, ship_date)
    _write_box_count(sheet, cartons)

    shipment = creator.get_shipment(inbound_plan_id, shipment_id)
    _write_shipment_confirmation_id(sheet, str(shipment.get("shipmentConfirmationId") or ""))
    return {
        "inboundPlanId": inbound_plan_id,
        "shipmentId": shipment_id,
        "shipmentConfirmationId": shipment.get("shipmentConfirmationId", ""),
        "destination": (shipment.get("destination") or {}).get("warehouseId", ""),
        "deliveryWindow": shipment.get("selectedDeliveryWindow") or {},
    }


def build_shipment_link(shipment_confirmation_id: str) -> str:
    """納品番号を Seller Central の納品詳細へのリンクにする"""
    return f'=HYPERLINK("{SHIPMENT_SUMMARY_URL}{shipment_confirmation_id}", "{shipment_confirmation_id}")'


def _write_shipment_confirmation_id(sheet: PurchaseSheet, shipment_confirmation_id: str) -> None:
    """「納品プラン」列を試作プランIDから納品番号(FBA…)へ差し替える。

    update_status_estimate / fill_sku_fnsku_from_shipment はこの列から shipment ID を読む。
    wf… のままだと在庫数・受領日・SKU/FNSKU が永久に入らない。
    """
    if not SHIPMENT_ID_PATTERN.fullmatch(shipment_confirmation_id):
        logger.warning("納品番号の形式が想定外のため書き込みません: %s", shipment_confirmation_id)
        return
    column = sheet._headers.index("納品プラン") + 1
    formula = build_shipment_link(shipment_confirmation_id)
    for row in sheet.data:
        sheet.write_formula(row.row_number, column, formula)
    logger.info("納品プラン列に %s を書き込みました (%d行)", shipment_confirmation_id, len(sheet.data))


def _resolve_inbound_plan_id(sheet: PurchaseSheet) -> str:
    if not sheet.data:
        raise RuntimeError("納品プランIDが取得できません: 対象行がありません")
    row = sheet.data[0]
    display_value = str(row.get("納品プラン") or "").strip()
    inbound_plan_id = extract_inbound_plan_id(display_value)
    if not is_full_inbound_plan_id(inbound_plan_id):
        formula = sheet.read_cell_formula(row.row_number, "納品プラン")
        inbound_plan_id = extract_inbound_plan_id(formula) or inbound_plan_id
    if not inbound_plan_id:
        raise RuntimeError("納品プランIDが取得できません: 「納品プラン」列が空です")
    if not is_full_inbound_plan_id(inbound_plan_id):
        raise RuntimeError(
            f"納品プランIDが短縮形のままです（取得値: {inbound_plan_id}）。"
            "「納品プラン」列のHYPERLINK数式にフルID（wf+UUID）が含まれているか確認してください。"
        )
    click.echo(f"納品プランID: {inbound_plan_id}")
    return inbound_plan_id


def _apply_packing(creator: InboundPlanCreator, inbound_plan_id: str, cartons: list[dict[str, Any]]) -> None:
    options = creator.list_packing_options(inbound_plan_id)
    if not options:
        raise RuntimeError("packingOptionが見つかりません")
    creator.confirm_packing_option(inbound_plan_id, str(options[0]["packingOptionId"]))

    packing_group_id = creator.get_packing_group_id(inbound_plan_id)
    items = creator.get_packing_group_items(inbound_plan_id, packing_group_id)
    box_count = sum(int(carton["count"]) for carton in cartons)
    creator.set_packing_information(inbound_plan_id, build_packing_body(packing_group_id, cartons))
    click.echo(f"梱包情報を登録: {box_count}箱 / {len(items)}SKU（Amazonが手動で輸送箱の中身を処理する）")


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
