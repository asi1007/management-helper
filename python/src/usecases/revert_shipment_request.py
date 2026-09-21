from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import click
import gspread
import httpx

from shared.config import AppConfig
from infrastructure.spreadsheet.base_row import BaseRow
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet

logger = logging.getLogger(__name__)

# 状態列は数式なので書かない。この4列を空にすれば ifs が「梱包依頼必要」に戻る。
# 受領開始日を残すと ifs が「受領中」を返し続ける
CLEARED_COLUMNS = ("梱包依頼日", "プラン別名", "納品プラン", "受領開始日")
FULL_PLAN_ID_PATTERN = r"wf[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}"
SELF_ACCOUNT_ID = 5437457
BODY_TEMPLATE = "【{category}】"
DELETED_BODY = "[deleted]"


@dataclass
class RevertPlan:
    alias: str
    rows: list[BaseRow]
    inbound_plan_ids: list[str] = field(default_factory=list)

    @property
    def row_numbers(self) -> list[int]:
        return [r.row_number for r in self.rows]


def build_revert_plan(rows: list[BaseRow], alias: str) -> RevertPlan:
    target = str(alias or "").strip()
    if not target:
        raise ValueError("プラン別名を指定してください")
    matched = [r for r in rows if str(r.get("プラン別名") or "").strip() == target]
    if not matched:
        raise ValueError(f"プラン別名「{target}」の行がありません")
    matched.sort(key=lambda r: r.row_number)
    return RevertPlan(alias=target, rows=matched, inbound_plan_ids=extract_inbound_plan_ids(matched))


def extract_inbound_plan_ids(rows: list[BaseRow]) -> list[str]:
    found: list[str] = []
    for row in rows:
        for plan_id in re.findall(FULL_PLAN_ID_PATTERN, str(row.get("納品プラン") or "")):
            if plan_id not in found:
                found.append(plan_id)
    return found


# batch-labels --air がプラン別名の末尾にだけ足す語。
# 指示書とラベルのファイル名は納品分類のままなので、照合語からは外す。
PLAN_NAME_SUFFIXES = ("空輸",)


def _strip_plan_name_suffix(category: str) -> str:
    for suffix in PLAN_NAME_SUFFIXES:
        if category.endswith(suffix):
            return category[: -len(suffix)]
    return category


def build_target_keywords(alias: str, year: int) -> list[str]:
    """プラン別名から、batch-labels がその回に送った投稿だけを見分ける語を作る。

    「09/15ファッション1」→ 本文「【ファッション1】」/ 指示書「0915ファッション1」/
    ラベル「2026-09-15_ファッション1」

    **末尾の「空輸」は落とす。** --air はプラン別名にしか付かず、
    投稿本文もファイル名も納品分類のままなので、付けたままだと永久に一致しない。
    指示書 xlsx は「0918ノーマル指示書.xlsx」なので日付付きの語からも落とす。

    **分類名を必ず含めること。** 同じ日に複数グループを送るので「梱包指示書」のような
    共通語で照合すると他グループや前日分まで巻き込む（2026-09-15 にドライランで7件拾った）。
    """
    target = _strip_plan_name_suffix(str(alias or "").strip())
    keywords = [target.replace("/", "")]
    matched = re.match(r"(\d{1,2})/(\d{1,2})(.*)", target)
    if matched:
        month, day, category = matched.groups()
        if category:
            keywords.append(BODY_TEMPLATE.format(category=category))
        keywords.append(f"{year}-{int(month):02d}-{int(day):02d}_{category}")
    else:
        keywords.append(BODY_TEMPLATE.format(category=target))
    return [k for k in keywords if k]


def select_chatwork_message_ids(
    messages: list[dict[str, Any]],
    *,
    account_id: int,
    since: int,
    keywords: list[str] | tuple[str, ...],
) -> list[str]:
    """自分が since 以降に送った、キーワードを含む投稿の message_id を返す"""
    selected: list[str] = []
    for message in messages:
        if (message.get("account") or {}).get("account_id") != account_id:
            continue
        if int(message.get("send_time") or 0) < since:
            continue
        body = str(message.get("body") or "")
        if not body or body == DELETED_BODY:
            continue
        if not any(word in body for word in keywords):
            continue
        selected.append(str(message["message_id"]))
    return selected


def revert_shipment_request(
    config: AppConfig,
    repo: BaseSheetsRepository,
    alias: str,
    *,
    dry_run: bool = True,
    delete_chatwork: bool = False,
    since_hours: int = 24,
) -> RevertPlan:
    sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    plan = build_revert_plan(sheet.all_data, alias)
    _echo_plan(plan)

    if delete_chatwork:
        _handle_chatwork(config, plan, dry_run=dry_run, since_hours=since_hours)

    if dry_run:
        click.echo("\n※ドライラン。--execute を付けると実際にクリアします")
        return plan

    _clear_columns(sheet, plan)
    click.echo(f"\n{len(plan.rows)}行を「梱包依頼必要」に戻しました")
    if plan.inbound_plan_ids:
        click.echo("試作納品プランは Seller Central で手動削除してください:")
        for plan_id in plan.inbound_plan_ids:
            click.echo(f"  https://sellercentral.amazon.co.jp/fba/sendtoamazon/confirm_content_step?wf={plan_id}")
    return plan


def _echo_plan(plan: RevertPlan) -> None:
    click.echo(f"対象: プラン別名「{plan.alias}」 {len(plan.rows)}行")
    for row in plan.rows:
        name = str(row.get("商品名") or "").strip()[:34]
        click.echo(f"  行{row.row_number}: {name} {row.get('購入数')}個")
    if plan.inbound_plan_ids:
        click.echo(f"試作納品プラン: {', '.join(plan.inbound_plan_ids)}")


def _clear_columns(sheet: PurchaseSheet, plan: RevertPlan) -> None:
    columns = {name: sheet._headers.index(name) + 1 for name in CLEARED_COLUMNS}
    batch = [
        {"range": gspread.utils.rowcol_to_a1(row.row_number, col), "values": [[""]]}
        for row in plan.rows
        for col in columns.values()
    ]
    sheet._worksheet.batch_update(batch, value_input_option="USER_ENTERED")
    logger.info("%d行 × %d列をクリアしました", len(plan.rows), len(columns))


def _handle_chatwork(config: AppConfig, plan: RevertPlan, *, dry_run: bool, since_hours: int) -> None:
    if not (config.chatwork_api_token and config.chatwork_room_id):
        click.echo("Chatwork未設定のため送付の取り下げはスキップします")
        return
    headers = {"X-ChatWorkToken": config.chatwork_api_token}
    base = f"https://api.chatwork.com/v2/rooms/{config.chatwork_room_id}/messages"
    response = httpx.get(base, headers=headers, params={"force": 1}, timeout=15.0)
    if response.status_code != 200:
        click.echo(f"Chatworkの取得に失敗しました: {response.status_code}")
        return
    now = datetime.now()
    since = int(now.timestamp()) - since_hours * 3600
    keywords = build_target_keywords(plan.alias, now.year)
    click.echo(f"照合する語: {keywords}")
    ids = select_chatwork_message_ids(
        response.json(), account_id=SELF_ACCOUNT_ID, since=since, keywords=keywords
    )
    if not ids:
        click.echo("取り下げ対象のChatwork投稿はありません")
        return
    click.echo(f"\nChatworkの取り下げ対象: {len(ids)}件 {ids}")
    if dry_run:
        return
    for message_id in ids:
        deleted = httpx.delete(f"{base}/{message_id}", headers=headers, timeout=15.0)
        click.echo(f"  {message_id}: {deleted.status_code}")
