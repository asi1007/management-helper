from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

import click

from shared.config import AppConfig
from domain.label.services.label_aggregator import LabelAggregator
from infrastructure.amazon.auth import get_auth_token
from infrastructure.amazon.downloader import Downloader
from infrastructure.spreadsheet.base_row import BaseRow
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.instruction_sheet import InstructionSheet
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet
from usecases.create_inspection_sheet import create_inspection_sheet_if_needed

logger = logging.getLogger(__name__)


def batch_print_labels(
    config: AppConfig, repo: BaseSheetsRepository, drive_service: Any
) -> None:
    access_token = get_auth_token(config.api_key, config.api_secret, config.refresh_token)

    sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    sheet.filter("状態", ["梱包依頼必要"])

    if not sheet.data:
        click.echo("梱包依頼必要の行がありません")
        return

    groups = _group_by_delivery_category(sheet.data)
    non_home_groups = {k: v for k, v in groups.items() if "自宅" not in k}

    if not non_home_groups:
        click.echo("自宅以外の納品分類グループがありません")
        return

    skipped = {k: v for k, v in groups.items() if "自宅" in k}
    if skipped:
        skipped_names = ", ".join(f"{k}({len(v)}行)" for k, v in skipped.items())
        click.echo(f"スキップ（自宅）: {skipped_names}")

    sheet.fill_missing_skus_from_asins(access_token)
    sheet.fetch_missing_fnskus(access_token)

    click.echo(f"\n{len(non_home_groups)}グループを処理します")
    click.echo("=" * 50)

    for category, rows in non_home_groups.items():
        click.echo(f"\n[{category}] {len(rows)}行")

        sheet.data = rows
        row_numbers = [r.row_number for r in rows]

        label_urls = _create_label_pdf(rows, access_token, drive_service)
        instruction_url = _create_instruction_sheet(config, repo, drive_service, rows)

        _write_to_sheet(sheet, instruction_url, label_urls, row_numbers)

        click.echo(f"  ラベル:")
        for url in label_urls:
            click.echo(f"    {url}")
        click.echo(f"  指示書: {instruction_url}")

    click.echo("\n" + "=" * 50)
    click.echo("全グループの処理が完了しました")


def _group_by_delivery_category(rows: list[BaseRow]) -> dict[str, list[BaseRow]]:
    groups: dict[str, list[BaseRow]] = defaultdict(list)
    for row in rows:
        category = str(row.get("納品分類") or "").strip()
        if not category:
            category = "未分類"
        groups[category].append(row)
    return dict(groups)


def _create_label_pdf(data: list[Any], access_token: str, drive_service: Any) -> list[str]:
    aggregator = LabelAggregator()
    items = aggregator.aggregate(data)
    downloader = Downloader(auth_token=access_token, drive_service=drive_service)
    date_str = datetime.now().strftime("%Y-%m-%d")
    sku_nums = [item.to_msku_quantity() for item in items]
    result = downloader.download_labels(sku_nums, date_str)
    return result.get("urls", [result["url"]])


def _create_instruction_sheet(
    config: AppConfig, repo: BaseSheetsRepository, drive_service: Any, data: list[Any]
) -> str:
    instruction = InstructionSheet(repo, drive_service, config.keepa_api_key)
    return instruction.create(data)


def _write_to_sheet(
    sheet: PurchaseSheet, instruction_url: str, label_urls: list[str], row_numbers: list[int]
) -> None:
    today = datetime.now().strftime("%Y/%m/%d")
    sheet.write_column_by_func("梱包依頼日", lambda _row, _i: today)
    try:
        sheet.write_plan_name_to_rows(instruction_url)
    except Exception as e:
        logger.warning("プラン別名列への書き込みでエラー: %s", e)
