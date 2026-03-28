from __future__ import annotations

import logging
from typing import Any

import click

from shared.config import AppConfig
from infrastructure.amazon.auth import get_auth_token
from infrastructure.amazon.inbound_plan_creator import InboundPlanCreator
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet
from infrastructure.spreadsheet.work_record_sheet import WorkRecordSheet

logger = logging.getLogger(__name__)


def create_inbound_plan(config: AppConfig, repo: BaseSheetsRepository, row_numbers: list[int]) -> None:
    access_token = get_auth_token(config.api_key, config.api_secret, config.refresh_token)
    sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    sheet.get_rows_by_numbers(row_numbers)
    sheet.fill_missing_skus_from_asins(access_token)
    items = sheet.aggregate_items()
    if not items:
        raise RuntimeError("納品対象のアイテムがありません")
    creator = InboundPlanCreator(access_token)
    plan_result = creator.create_plan(items)
    sheet.write_plan_result(plan_result)
    _record_to_work_record(config, repo, plan_result, sheet)
    click.echo(f"納品プラン作成完了: {plan_result.get('inboundPlanId', '')}")
    click.echo(f"リンク: {plan_result.get('link', '')}")


def create_inbound_plan_with_placement(config: AppConfig, repo: BaseSheetsRepository, row_numbers: list[int]) -> None:
    access_token = get_auth_token(config.api_key, config.api_secret, config.refresh_token)
    sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    sheet.get_rows_by_numbers(row_numbers)
    sheet.fill_missing_skus_from_asins(access_token)
    items = sheet.aggregate_items()
    if not items:
        raise RuntimeError("納品対象のアイテムがありません")
    creator = InboundPlanCreator(access_token)
    plan_result = creator.create_plan(items)
    inbound_plan_id = plan_result.get("inboundPlanId", "")
    options = creator.get_placement_options(inbound_plan_id)
    placement_options = options.get("placementOptions", [])
    if not placement_options:
        click.echo("Placement Optionがありません。デフォルトで続行します。")
    else:
        for i, opt in enumerate(placement_options):
            opt_id = opt.get("placementOptionId", "")
            fees = opt.get("fees", [])
            click.echo(f"  {i + 1}: {opt_id} (fees: {fees})")
        choice = click.prompt("Placement Optionを番号で選択", type=int) - 1
        if 0 <= choice < len(placement_options):
            selected_id = placement_options[choice].get("placementOptionId", "")
            creator.confirm_placement_option(inbound_plan_id, selected_id)
            click.echo(f"Placement Option確定: {selected_id}")
    sheet.write_plan_result(plan_result)
    _record_to_work_record(config, repo, plan_result, sheet)
    click.echo(f"納品プラン作成完了: {inbound_plan_id}")


def _record_to_work_record(
    config: AppConfig, repo: BaseSheetsRepository,
    plan_result: dict[str, Any], sheet: PurchaseSheet,
) -> None:
    asin_records: list[dict[str, Any]] = []
    for row in sheet.data:
        asin = str(row.get("ASIN") or "").strip()
        qty = int(row.get("購入数") or 0)
        try:
            order_no = str(row.get("注文番号") or "").strip()
        except Exception:
            order_no = ""
        if asin and qty > 0:
            asin_records.append({"asin": asin, "quantity": qty, "orderNumber": order_no})
    if asin_records:
        work_record = WorkRecordSheet(repo, config.sheet_id, config.work_record_sheet_name)
        work_record.append_inbound_plan_summary(plan_result, asin_records)
