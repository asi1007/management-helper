from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import click

from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet
from infrastructure.spreadsheet.sales_sheet import SalesSheet
from shared.config import AppConfig

REMARK_HEADER = "備考"


@dataclass(frozen=True)
class RemarkSyncPlan:
    row_number: int
    asin: str
    remark: str


def build_remark_sync_plan(
    rows: list[Any],
    remark_by_asin: dict[str, str],
    row_numbers: list[int] | None = None,
    overwrite: bool = False,
) -> list[RemarkSyncPlan]:
    """売上/日の備考を仕入管理へ写す計画を作る。

    備考（梱包指示）の正本は売上/日で、仕入管理へは発注時に auto-order がコピーする。
    発注（#5）は梱包方法の決定（#7）より先なので、初回仕入れの行は空のまま残る。

    既存の備考は既定で触らない。仕入管理の備考はロット別で、
    同じ商品でも行ごとに色・仕様が違う（行189は磨砂、行190は透明）。
    """
    if row_numbers is not None:
        available = {r.row_number for r in rows}
        missing = sorted(set(row_numbers) - available)
        if missing:
            raise ValueError(f"仕入管理に見つかりません: {missing}")
        rows = [r for r in rows if r.row_number in set(row_numbers)]

    plans: list[RemarkSyncPlan] = []
    for row in rows:
        asin = str(row.get("ASIN") or "").strip()
        if not asin:
            continue
        current = str(row.get(REMARK_HEADER) or "").strip()
        if current and not overwrite:
            continue
        incoming = str(remark_by_asin.get(asin) or "").strip()
        if not incoming or incoming == current:
            continue
        plans.append(RemarkSyncPlan(row.row_number, asin, incoming))
    return plans


def sync_remarks(
    config: AppConfig,
    repo: BaseSheetsRepository,
    row_numbers: list[int] | None = None,
    overwrite: bool = False,
    dry_run: bool = False,
) -> list[RemarkSyncPlan]:
    sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    remark_by_asin = SalesSheet(repo).load_remark_by_asin()
    plans = build_remark_sync_plan(sheet.data, remark_by_asin, row_numbers, overwrite)

    if not plans:
        click.echo("写す備考はありません")
        return plans

    for plan in plans:
        head = plan.remark.splitlines()[0]
        click.echo(f"行{plan.row_number} {plan.asin}: {head[:60]}")
    if dry_run:
        click.echo(f"\n--dry-run のため書いていません（{len(plans)}行）")
        return plans

    sheet.update_cells(
        [(plan.row_number, REMARK_HEADER, plan.remark) for plan in plans]
    )
    click.echo(f"\n{len(plans)}行の備考を仕入管理へ写しました")
    return plans
