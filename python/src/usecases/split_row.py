from __future__ import annotations

import logging

import click

from shared.config import AppConfig
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.home_shipment_sheet import HomeShipmentSheet
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet

logger = logging.getLogger(__name__)


def split_row(config: AppConfig, repo: BaseSheetsRepository, row_numbers: list[int]) -> None:
    home_sheet = HomeShipmentSheet(repo, config.sheet_id, config.home_shipment_sheet_name)
    home_sheet.get_rows_by_numbers(row_numbers)
    purchase_row_numbers = home_sheet.get_row_numbers_column()
    if not purchase_row_numbers:
        raise RuntimeError("行番号が取得できません")
    purchase_sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    purchase_sheet.filter("行番号", purchase_row_numbers)
    if not purchase_sheet.data:
        raise RuntimeError("対応する行が見つかりません")
    delivery_qty = click.prompt("納品数を入力してください", type=int)
    if delivery_qty <= 0:
        raise ValueError("有効な納品数を入力してください")
    qty_col = purchase_sheet._get_column_index_by_name("購入数") + 1
    for row in purchase_sheet.data:
        current_qty = int(purchase_sheet._worksheet.cell(row.row_number, qty_col).value or 0)
        if delivery_qty >= current_qty:
            logger.warning("納品数(%d)が購入数(%d)以上です。スキップ。", delivery_qty, current_qty)
            continue
        new_qty = current_qty - delivery_qty
        purchase_sheet.write_cell(row.row_number, qty_col, new_qty)
        purchase_sheet._worksheet.insert_row(
            [row[i] for i in range(len(row))],
            row.row_number + 1,
        )
        purchase_sheet.write_cell(row.row_number + 1, qty_col, delivery_qty)
        logger.info("行%d: %d -> %d + %d", row.row_number, current_qty, new_qty, delivery_qty)
    click.echo("行分割完了")
