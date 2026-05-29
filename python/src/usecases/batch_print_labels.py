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
from usecases.create_inspection_sheet import create_inspection_sheet_if_needed

logger = logging.getLogger(__name__)


def batch_print_labels(
    config: AppConfig, repo: BaseSheetsRepository, category_filter: list[str] | None = None
) -> None:
    access_token = get_auth_token(config.api_key, config.api_secret, config.refresh_token)

    sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    sheet.filter("状態", ["梱包依頼必要"])

    if not sheet.data:
        click.echo("梱包依頼必要の行がありません")
        return

    groups = _group_by_delivery_category(sheet.data)
    if category_filter:
        non_home_groups = {}
        for cat in category_filter:
            if cat in groups:
                non_home_groups[cat] = groups[cat]
            else:
                click.echo(f"警告: 納品分類「{cat}」の行がありません")
    else:
        non_home_groups = {k: v for k, v in groups.items() if "自宅" not in k}

    if not non_home_groups:
        return

    non_home_rows = [r for rows in non_home_groups.values() for r in rows]
    sheet.data = non_home_rows

    from infrastructure.spreadsheet.sales_sheet import SalesSheet
    sales = SalesSheet(repo)
    asin_map = sales.load_asin_to_sku_fnsku()
    sheet.fill_missing_sku_fnsku_from_sales(asin_map)
    _validate_no_blank_sku(sheet.data)

    click.echo(f"\n{len(non_home_groups)}グループを処理します")
    click.echo("=" * 50)

    group_results: list[dict[str, Any]] = []

    for category, rows in non_home_groups.items():
        click.echo(f"\n[{category}] {len(rows)}行")

        sheet.data = rows
        is_home = "自宅" in category

        if is_home:
            label_paths = []
            inspection_path = None
        else:
            label_paths = _create_label_pdf(rows, access_token, config, category)
            inspection_path = _create_inspection_sheet(config, repo, rows, category)
        instruction_path = _create_instruction_sheet(config, rows)

        _write_to_sheet(sheet, str(instruction_path))

        if label_paths:
            click.echo("  ラベル:")
            for p in label_paths:
                click.echo(f"    {p}")
        click.echo(f"  指示書: {instruction_path}")
        if inspection_path:
            click.echo(f"  検品指示書: {inspection_path}")

        group_results.append({
            "category": category,
            "row_count": len(rows),
            "label_paths": label_paths,
            "instruction_path": str(instruction_path),
            "inspection_path": str(inspection_path) if inspection_path else None,
        })

    click.echo("\n" + "=" * 50)
    _print_summary(non_home_groups)
    click.echo("全グループの処理が完了しました")

    if config.chatwork_api_token and config.chatwork_room_id:
        _send_chatwork_by_group(config, group_results)
    else:
        click.echo("\nChatwork送信: CHATWORK_API_TOKEN/CHATWORK_ROOM_ID未設定のためスキップ")


def _validate_no_blank_sku(rows: list[BaseRow]) -> None:
    _validate_sku_fnsku(rows)


def _detect_missing_rows(requested_rows: list[BaseRow], processed_row_numbers: list[int]) -> list[int]:
    """依頼対象に含まれていたが、処理 (ラベル生成や指示書登載) で漏れた行番号を返す"""
    processed_set = set(processed_row_numbers)
    missing: list[int] = []
    for row in requested_rows:
        if row.row_number not in processed_set:
            missing.append(row.row_number)
    return missing


def _verify_label_quantity(items: list[dict], actual_pages: int) -> None:
    """ラベル PDF ページ数が指示書 SKU 数量から計算した期待値と乖離していたらエラー"""
    import math
    expected = sum(math.ceil(int(it["quantity"]) / 40) for it in items if int(it.get("quantity", 0)) > 0)
    if expected == 0:
        return
    diff = abs(actual_pages - expected)
    tolerance = max(int(expected * 0.2), 2)  # 20% or 2ページ
    if diff > tolerance:
        raise RuntimeError(
            f"ラベル数と指示書数量の不一致 (乖離): 期待ページ={expected}, 実ページ={actual_pages}, 差={diff}, 許容={tolerance}。"
            "SKU集約・ラベル分割・SP-API応答のいずれかの不整合の可能性。"
        )


def _validate_sku_fnsku(rows: list[BaseRow]) -> None:
    blank_sku: list[int] = []
    blank_fnsku: list[int] = []
    for row in rows:
        sku = str(row.get("SKU") or "").strip()
        fnsku = str(row.get("FNSKU") or "").strip()
        if not sku:
            blank_sku.append(row.row_number)
        if not fnsku:
            blank_fnsku.append(row.row_number)

    errors: list[str] = []
    if blank_sku:
        errors.append(f"SKU空白の行: {', '.join(str(r) for r in blank_sku)}")
    if blank_fnsku:
        errors.append(f"FNSKU空白の行: {', '.join(str(r) for r in blank_fnsku)}")
    if errors:
        raise RuntimeError(
            "SKU/FNSKU検証エラー: " + " / ".join(errors) +
            "。Amazon側でSKU/FNSKUを発行してから再実行してください。"
        )



def _check_fc_split_for_all_groups(
    non_home_groups: dict[str, list[BaseRow]],
    creator: Any,
    sheet: Any,
) -> None:
    """各グループで試作プランを作成し packingGroups の数を取得。1グループ→URL書き込み、2+→RuntimeError"""
    split_reports: list[str] = []
    plan_results: list[tuple[str, list[BaseRow], str, str]] = []  # (category, rows, plan_id, plan_url)

    for category, rows in non_home_groups.items():
        items = _build_items_from_rows(rows)
        result = creator.create_plan(items)
        plan_id = result["inboundPlanId"]
        plan_url = result["link"]

        groups = creator.get_packing_groups(plan_id)
        if len(groups) > 1:
            sku_to_row = {str(r.get("SKU") or "").strip(): r.row_number for r in rows}
            split_reports.append(_format_split_report(category, plan_id, plan_url, groups, sku_to_row))
        else:
            plan_results.append((category, rows, plan_id, plan_url))

    if split_reports:
        click.echo("\n".join(split_reports), err=True)
        raise RuntimeError(
            f"FC分割を検知 ({len(split_reports)}グループ)。"
            "仕入管理シートの「納品分類」列をグループ別に書き換えてから再実行してください。"
        )

    for _category, rows, plan_id, plan_url in plan_results:
        sheet.write_trial_plan_url(rows, plan_url, plan_id)


def _build_items_from_rows(rows: list[BaseRow]) -> dict[str, dict[str, Any]]:
    aggregated: dict[str, dict[str, Any]] = {}
    for row in rows:
        sku = str(row.get("SKU") or "").strip()
        asin = str(row.get("ASIN") or "").strip()
        try:
            quantity = int(row.get("購入数") or 0)
        except (ValueError, TypeError):
            quantity = 0
        if not sku or quantity <= 0:
            continue
        if sku not in aggregated:
            aggregated[sku] = {"msku": sku, "asin": asin, "quantity": 0, "labelOwner": "SELLER"}
        aggregated[sku]["quantity"] += quantity
    return aggregated


def _format_split_report(
    category: str,
    plan_id: str,
    plan_url: str,
    packing_groups: list[dict[str, Any]],
    sku_to_row: dict[str, int],
) -> str:
    lines = [f"\n[{category}] 試作プラン: {plan_id} ({len(packing_groups)}グループに分割)"]
    for i, pg in enumerate(packing_groups, 1):
        pg_id = pg.get("packingGroupId", "")
        items = pg.get("items", [])
        skus = [str(it.get("msku", "")).strip() for it in items if it.get("msku")]
        row_numbers = sorted({sku_to_row[s] for s in skus if s in sku_to_row})
        rows_str = ", ".join(str(r) for r in row_numbers) if row_numbers else "(行不明)"
        lines.append(f"  グループ{i} ({pg_id}): 行{rows_str} ({len(skus)} SKUs)")
    lines.append(f"  プランURL: {plan_url}")
    return "\n".join(lines)


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
    paths = result.get("paths", [result["path"]])
    _check_label_pdf_pages(paths, sku_nums, category)
    return paths


def _check_label_pdf_pages(pdf_paths: list[str], sku_nums: list[dict], category: str) -> None:
    """PDF合計ページ数 vs SKU別ceil(qty/40)合計 を検証。乖離があれば RuntimeError"""
    total_pages = 0
    for p in pdf_paths:
        try:
            from pypdf import PdfReader
            total_pages += len(PdfReader(p).pages)
        except ImportError:
            try:
                import subprocess
                out = subprocess.check_output(["mdls", "-name", "kMDItemNumberOfPages", "-raw", p], timeout=10).decode().strip()
                if out and out.isdigit():
                    total_pages += int(out)
            except Exception as e:
                logger.warning("PDFページ数取得失敗 (%s): %s -> 検証スキップ", p, e)
                return
        except Exception as e:
            logger.warning("PDFページ数取得失敗 (%s): %s -> 検証スキップ", p, e)
            return
    items = [{"sku": s.get("msku", ""), "quantity": s.get("quantity", 0)} for s in sku_nums]
    try:
        _verify_label_quantity(items, total_pages)
        logger.info("[%s] ラベル検証OK: 期待=SKU別ceil合計, 実=%dページ", category, total_pages)
    except RuntimeError as e:
        click.echo(f"⚠️ [{category}] {e}", err=True)
        raise


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


def _create_inspection_sheet(
    config: AppConfig, repo: BaseSheetsRepository, data: list[Any], category: str
) -> Path | None:
    return create_inspection_sheet_if_needed(config, repo, data, category)


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
    msg_url = f"https://api.chatwork.com/v2/rooms/{config.chatwork_room_id}/messages"
    file_url = f"https://api.chatwork.com/v2/rooms/{config.chatwork_room_id}/files"

    for i, group in enumerate(group_results):
        category = group["category"]
        row_count = group["row_count"]
        message = f"{to_tag}【{category}】{row_count}件の梱包指示書を作成したので送付します。"

        # メッセージを先に送信
        response = httpx.post(msg_url, headers=headers, data={"body": message, "self_unread": 0}, timeout=10.0)
        if response.status_code == 200:
            click.echo(f"  Chatworkメッセージ [{category}]")
        else:
            click.echo(f"  Chatworkメッセージエラー [{category}]: {response.status_code}")
        time.sleep(1)

        # ファイルを順次送信
        file_paths = group["label_paths"] + [group["instruction_path"]]
        if group.get("inspection_path"):
            file_paths.append(group["inspection_path"])

        for file_path in file_paths:
            path = Path(file_path)
            if not path.exists():
                continue
            with open(path, "rb") as f:
                files = {"file": (path.name, f, _guess_content_type(path))}
                response = httpx.post(file_url, headers=headers, files=files, data={"message": ""}, timeout=30.0)
            if response.status_code == 200:
                click.echo(f"  Chatworkファイル [{category}]: {path.name}")
            else:
                click.echo(f"  Chatworkファイルエラー ({path.name}): {response.status_code} {response.text}")
            time.sleep(1)

        # 次のグループとの間隔
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
