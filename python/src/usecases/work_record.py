from __future__ import annotations

import logging
from datetime import datetime

import click

from shared.config import AppConfig
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.home_shipment_sheet import HomeShipmentSheet
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet
from infrastructure.spreadsheet.work_record_sheet import WorkRecordSheet

logger = logging.getLogger(__name__)


def record_work_start(config: AppConfig, repo: BaseSheetsRepository, row_numbers: list[int]) -> None:
    home_sheet = HomeShipmentSheet(repo, config.sheet_id, config.home_shipment_sheet_name)
    home_sheet.get_rows_by_numbers(row_numbers)
    work_record = WorkRecordSheet(repo, config.sheet_id, config.work_record_sheet_name)
    timestamp = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    for row in home_sheet.data:
        asin = str(row.get("ASIN") or "").strip()
        purchase_date = str(row.get("購入日") or "").strip()
        try:
            order_number = str(row.get("注文番号") or "").strip()
        except Exception:
            order_number = ""
        if not asin:
            logger.warning("ASINが空の行をスキップしました")
            continue
        work_record.append_record(asin, purchase_date, "開始", timestamp, order_number=order_number)
    logger.info("%d件の作業記録（開始）を追加しました", len(home_sheet.data))


def record_work_end(config: AppConfig, repo: BaseSheetsRepository, row_numbers: list[int]) -> None:
    home_sheet = HomeShipmentSheet(repo, config.sheet_id, config.home_shipment_sheet_name)
    home_sheet.get_rows_by_numbers(row_numbers)
    work_record = WorkRecordSheet(repo, config.sheet_id, config.work_record_sheet_name)
    timestamp = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    for row in home_sheet.data:
        asin = str(row.get("ASIN") or "").strip()
        purchase_date = str(row.get("購入日") or "").strip()
        try:
            order_number = str(row.get("注文番号") or "").strip()
        except Exception:
            order_number = ""
        if not asin:
            logger.warning("ASINが空の行をスキップしました")
            continue
        work_record.append_record(asin, purchase_date, "終了", timestamp, order_number=order_number)
    logger.info("%d件の作業記録（終了）を追加しました", len(home_sheet.data))


def record_defect(config: AppConfig, repo: BaseSheetsRepository, row_numbers: list[int]) -> None:
    home_sheet = HomeShipmentSheet(repo, config.sheet_id, config.home_shipment_sheet_name)
    defect_reasons = home_sheet.get_defect_reason_list()
    if not defect_reasons:
        raise RuntimeError("不良原因リストが見つかりません")
    home_sheet.get_rows_by_numbers(row_numbers)
    if not home_sheet.data:
        raise RuntimeError("選択された行がありません")
    row_info = []
    for row in home_sheet.data:
        try:
            order_number = str(row.get("注文番号") or "").strip()
        except Exception:
            order_number = ""
        row_info.append({
            "purchase_row_number": str(row.get("行番号") or "").strip(),
            "asin": str(row.get("ASIN") or "").strip(),
            "purchase_date": str(row.get("購入日") or "").strip(),
            "order_number": order_number,
        })
    quantity = click.prompt("不良数を入力してください", type=int)
    if quantity <= 0:
        raise ValueError("有効な不良数を入力してください")
    reason_list = "\n".join(f"{i + 1}: {r}" for i, r in enumerate(defect_reasons))
    reason_index = click.prompt(f"原因を番号で選択してください:\n{reason_list}", type=int) - 1
    if reason_index < 0 or reason_index >= len(defect_reasons):
        raise ValueError("有効な番号を入力してください")
    selected_reason = defect_reasons[reason_index]
    comment = click.prompt("コメント（任意、空欄可）", default="", show_default=False) or None
    purchase_row_numbers = [info["purchase_row_number"] for info in row_info if info["purchase_row_number"]]
    purchase_sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    purchase_sheet.filter("行番号", purchase_row_numbers)
    if not purchase_sheet.data:
        raise RuntimeError("仕入管理シートに対応する行が見つかりません")
    zero_rows = purchase_sheet.decrease_purchase_quantity(quantity)
    if zero_rows:
        purchase_sheet.delete_rows(zero_rows)
    work_record = WorkRecordSheet(repo, config.sheet_id, config.work_record_sheet_name)
    timestamp = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    for info in row_info:
        if not info["asin"]:
            continue
        work_record.append_record(
            info["asin"], info["purchase_date"], "不良", timestamp,
            quantity=quantity, reason=selected_reason, comment=comment,
            order_number=info["order_number"],
        )
    logger.info("%d件の不良品記録を追加しました", len(row_info))
    click.echo(f"不良品登録完了。不良数: {quantity}, 原因: {selected_reason}")
