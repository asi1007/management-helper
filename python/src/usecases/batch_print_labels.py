from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import click
import httpx

from shared.config import AppConfig
from domain.label.services.label_aggregator import LabelAggregator
from infrastructure.amazon.auth import get_auth_token
from infrastructure.amazon.downloader import Downloader
from infrastructure.spreadsheet.base_row import BaseRow
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.instruction_sheet import InstructionSheet
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet

logger = logging.getLogger(__name__)


def batch_print_labels(config: AppConfig, repo: BaseSheetsRepository) -> None:
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

    non_home_rows = [r for rows in non_home_groups.values() for r in rows]
    sheet.data = non_home_rows
    sheet.fill_missing_skus_from_asins(access_token)
    _validate_no_blank_sku(sheet.data)
    sheet.fetch_missing_fnskus(access_token)

    click.echo(f"\n{len(non_home_groups)}グループを処理します")
    click.echo("=" * 50)

    group_results: list[dict[str, Any]] = []

    for category, rows in non_home_groups.items():
        click.echo(f"\n[{category}] {len(rows)}行")

        sheet.data = rows

        label_paths = _create_label_pdf(rows, access_token, config, category)
        instruction_path = _create_instruction_sheet(config, rows)

        _write_to_sheet(sheet, str(instruction_path))

        click.echo("  ラベル:")
        for p in label_paths:
            click.echo(f"    {p}")
        click.echo(f"  指示書: {instruction_path}")

        group_results.append({
            "category": category,
            "row_count": len(rows),
            "label_paths": label_paths,
            "instruction_path": str(instruction_path),
        })

    click.echo("\n" + "=" * 50)
    _print_summary(non_home_groups)
    click.echo("全グループの処理が完了しました")

    if config.chatwork_api_token and config.chatwork_room_id:
        _send_chatwork_by_group(config, group_results)
    else:
        click.echo("\nChatwork送信: CHATWORK_API_TOKEN/CHATWORK_ROOM_ID未設定のためスキップ")


def _validate_no_blank_sku(rows: list[BaseRow]) -> None:
    blank_rows: list[int] = []
    for row in rows:
        sku = str(row.get("SKU") or "").strip()
        if not sku:
            blank_rows.append(row.row_number)
    if blank_rows:
        row_str = ", ".join(str(r) for r in blank_rows)
        raise RuntimeError(f"SKUが空白の行があります（行番号: {row_str}）。SKUを入力してから再実行してください。")


def _group_by_delivery_category(rows: list[BaseRow]) -> dict[str, list[BaseRow]]:
    groups: dict[str, list[BaseRow]] = defaultdict(list)
    for row in rows:
        category = str(row.get("納品分類") or "").strip()
        if not category:
            category = "未分類"
        groups[category].append(row)
    return dict(groups)


def _create_label_pdf(data: list[Any], access_token: str, config: AppConfig, category: str) -> list[str]:
    aggregator = LabelAggregator()
    items = aggregator.aggregate(data)
    save_dir = Path(config.label_dir)
    downloader = Downloader(auth_token=access_token, save_dir=save_dir)
    date_str = datetime.now().strftime("%Y-%m-%d")
    file_name = f"{date_str}_{category}"
    sku_nums = [item.to_msku_quantity() for item in items]
    result = downloader.download_labels(sku_nums, file_name)
    return result.get("paths", [result["path"]])


def _print_summary(groups: dict[str, list[BaseRow]]) -> None:
    click.echo("\n[集計]")
    total_weight = 0.0
    total_shipping = 0.0
    total_duty = 0.0

    for category, rows in groups.items():
        cat_weight = 0.0
        cat_shipping = 0.0
        cat_duty = 0.0

        for row in rows:
            qty = _to_float(row.get("購入数"))
            cat_weight += _to_float(row.get("重量")) * qty
            cat_shipping += _to_float(row.get("送料")) * qty
            cat_duty += _to_float(row.get("関税合計")) * qty

        click.echo(f"  [{category}] 重量合計: {cat_weight:.2f}  送料合計: {cat_shipping:.0f}  関税合計: {cat_duty:.0f}")
        total_weight += cat_weight
        total_shipping += cat_shipping
        total_duty += cat_duty

    click.echo(f"  [合計]   重量合計: {total_weight:.2f}  送料合計: {total_shipping:.0f}  関税合計: {total_duty:.0f}")
    click.echo("")


def _to_float(value: Any) -> float:
    try:
        return float(str(value).replace(",", "").strip()) if value else 0.0
    except (ValueError, TypeError):
        return 0.0


def _create_instruction_sheet(config: AppConfig, data: list[Any]) -> Path:
    save_dir = Path(config.instruction_dir)
    instruction = InstructionSheet(save_dir=save_dir, keepa_api_key=config.keepa_api_key)
    return instruction.create(data)


def _write_to_sheet(sheet: PurchaseSheet, instruction_path: str) -> None:
    today = datetime.now().strftime("%Y/%m/%d")
    sheet.write_column_by_func("梱包依頼日", lambda _row, _i: today)
    try:
        sheet.write_plan_name_to_rows(instruction_path)
    except Exception as e:
        logger.warning("プラン別名列への書き込みでエラー: %s", e)


def _send_chatwork_by_group(config: AppConfig, group_results: list[dict[str, Any]]) -> None:
    import time

    to_tag = ""
    if config.chatwork_to_account_id:
        to_tag = f"[To:{config.chatwork_to_account_id}]徐雪蘭さん\n"

    headers = {"X-ChatWorkToken": config.chatwork_api_token}
    file_url = f"https://api.chatwork.com/v2/rooms/{config.chatwork_room_id}/files"

    for i, group in enumerate(group_results):
        category = group["category"]
        row_count = group["row_count"]
        message = f"{to_tag}【{category}】{row_count}件の梱包指示書を作成したので送付します。"

        file_paths = group["label_paths"] + [group["instruction_path"]]
        first = True
        for file_path in file_paths:
            path = Path(file_path)
            if not path.exists():
                continue
            with open(path, "rb") as f:
                files = {"file": (path.name, f, _guess_content_type(path))}
                data = {"message": message if first else ""}
                response = httpx.post(file_url, headers=headers, files=files, data=data, timeout=30.0)
            if response.status_code == 200:
                click.echo(f"  Chatwork送信 [{category}]: {path.name}")
            else:
                click.echo(f"  Chatwork送信エラー ({path.name}): {response.status_code} {response.text}")
            first = False
            time.sleep(0.5)

        if i < len(group_results) - 1:
            time.sleep(2)

    click.echo("Chatwork送信完了")


def _guess_content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "application/pdf"
    if suffix == ".xlsx":
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return "application/octet-stream"
