from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import click

from shared.config import AppConfig
from domain.label.services.label_aggregator import LabelAggregator
from infrastructure.amazon.auth import get_auth_token
from infrastructure.amazon.downloader import Downloader
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.instruction_sheet import InstructionSheet
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet
from usecases.create_inspection_sheet import create_inspection_sheet_if_needed

logger = logging.getLogger(__name__)


def generate_labels_and_instructions(
    config: AppConfig, repo: BaseSheetsRepository, drive_service: Any, row_numbers: list[int]
) -> None:
    access_token = get_auth_token(config.api_key, config.api_secret, config.refresh_token)
    sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    sheet.get_rows_by_numbers(row_numbers)
    sheet.fill_missing_skus_from_asins(access_token)
    sheet.fetch_missing_fnskus(access_token)
    inspection_url = create_inspection_sheet_if_needed(config, repo, drive_service, sheet.data)
    if inspection_url:
        sheet.write_formula(2, 3, f'=HYPERLINK("{inspection_url}", "検品シート")')
    label_urls = _create_label_pdf(sheet.data, access_token, drive_service)
    instruction_url = _create_instruction_sheet(config, repo, drive_service, sheet.data)
    _write_to_sheet(sheet, instruction_url, label_urls)


def _create_label_pdf(data: list[Any], access_token: str, drive_service: Any) -> list[str]:
    aggregator = LabelAggregator()
    items = aggregator.aggregate(data)
    downloader = Downloader(auth_token=access_token, drive_service=drive_service)
    date_str = datetime.now().strftime("%Y-%m-%d")
    sku_nums = [item.to_msku_quantity() for item in items]
    result = downloader.download_labels(sku_nums, date_str)
    urls = result.get("urls", [result["url"]])
    if len(urls) > 1:
        click.echo(f"ラベル分割ダウンロード完了: {len(urls)}件のPDFを作成しました")
    return urls


def _create_instruction_sheet(
    config: AppConfig, repo: BaseSheetsRepository, drive_service: Any, data: list[Any]
) -> str:
    instruction = InstructionSheet(repo, drive_service, config.keepa_api_key)
    return instruction.create(data)


def _write_to_sheet(sheet: PurchaseSheet, instruction_url: str, label_urls: list[str]) -> None:
    today = datetime.now().strftime("%Y/%m/%d")
    sheet.write_column_by_func("梱包依頼日", lambda _row, _i: today)
    try:
        sheet.write_plan_name_to_rows(instruction_url)
    except Exception as e:
        logger.warning("プラン別名列への書き込みでエラー: %s", e)
    if len(label_urls) == 1:
        sheet.write_formula(2, 1, f'=HYPERLINK("{label_urls[0]}", "ラベルデータ")')
    else:
        for i, url in enumerate(label_urls):
            sheet.write_formula(2 + i, 1, f'=HYPERLINK("{url}", "ラベル{i + 1}/{len(label_urls)}")')
    sheet.write_formula(2, 2, f'=HYPERLINK("{instruction_url}", "指示書")')
