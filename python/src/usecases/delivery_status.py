from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import click

from domain.shipment.delivery_stage import DeliveryStage, classify_stage
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet
from shared.config import AppConfig

DEFAULT_STALE_DAYS = 14
DATE_PATTERN = re.compile(r"(\d{1,2})[-/](\d{1,2})")
# 工程ごとに「何単位で見たいか」が違う。仕入は発注、依頼は納品分類、納品はプラン。
GROUP_COLUMN = {
    DeliveryStage.AWAITING_SUPPLIER: ("注文番号", "(注文番号なし)"),
    DeliveryStage.AWAITING_SHIPMENT: ("納品分類", "(納品分類なし)"),
    DeliveryStage.AWAITING_AMAZON: ("プラン別名", "(プラン別名なし)"),
}
ELAPSED_FROM = {
    DeliveryStage.AWAITING_SUPPLIER: "購入日",
    DeliveryStage.AWAITING_SHIPMENT: "到着日",
    DeliveryStage.AWAITING_AMAZON: "発送日",
}


@dataclass(frozen=True)
class StageEntry:
    row_number: int
    group: str
    product_name: str
    quantity: int
    since: str
    elapsed: int | None
    shipment_id: str


@dataclass
class StageReport:
    stage: DeliveryStage
    entries: list[StageEntry] = field(default_factory=list)
    stale_days: int = DEFAULT_STALE_DAYS

    @property
    def row_count(self) -> int:
        return len(self.entries)

    @property
    def total_quantity(self) -> int:
        return sum(e.quantity for e in self.entries)

    @property
    def stale_count(self) -> int:
        return sum(1 for e in self.entries if e.elapsed is not None and e.elapsed > self.stale_days)


def elapsed_days(value: str, today: date) -> int | None:
    matched = DATE_PATTERN.search(str(value or "").strip())
    if not matched:
        return None
    month, day = int(matched.group(1)), int(matched.group(2))
    try:
        started = date(today.year, month, day)
    except ValueError:
        return None
    if started > today:  # 「12-31」のような年跨ぎは前年とみなす
        try:
            started = date(today.year - 1, month, day)
        except ValueError:
            return None
    return (today - started).days


def group_key_for(row: Any, stage: DeliveryStage) -> str:
    column, fallback = GROUP_COLUMN[stage]
    return str(row.get(column) or "").strip() or fallback


def _to_int(value: Any) -> int:
    try:
        return int(str(value or "0").strip() or 0)
    except ValueError:
        return 0


def build_reports(
    rows: list[Any], *, today: date, stale_days: int = DEFAULT_STALE_DAYS
) -> list[StageReport]:
    buckets: dict[DeliveryStage, StageReport] = {}
    for row in rows:
        stage = classify_stage(row)
        if stage is None or stage is DeliveryStage.DONE:
            continue
        since = str(row.get(ELAPSED_FROM[stage]) or "").strip()
        entry = StageEntry(
            row_number=row.row_number,
            group=group_key_for(row, stage),
            product_name=str(row.get("商品名") or "").strip(),
            quantity=_to_int(row.get("購入数")),
            since=since,
            elapsed=elapsed_days(since, today),
            shipment_id=str(row.get("納品プラン") or "").strip(),
        )
        buckets.setdefault(stage, StageReport(stage=stage, stale_days=stale_days)).entries.append(entry)

    for report in buckets.values():
        report.entries.sort(key=lambda e: (-(e.elapsed if e.elapsed is not None else -1), e.row_number))
    return [buckets[s] for s in DeliveryStage if s in buckets]


def show_delivery_status(
    config: AppConfig,
    repo: BaseSheetsRepository,
    *,
    stale_days: int = DEFAULT_STALE_DAYS,
    today: date | None = None,
) -> list[StageReport]:
    sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    reports = build_reports(sheet.all_data, today=today or date.today(), stale_days=stale_days)
    _print_reports(reports, stale_days)
    return reports


def _print_reports(reports: list[StageReport], stale_days: int) -> None:
    if not reports:
        click.echo("対応中の納品はありません")
        return
    for report in reports:
        stale = f" / {stale_days}日超 {report.stale_count}件" if report.stale_count else ""
        click.echo(f"\n=== {report.stage.label} ({report.row_count}行 / {report.total_quantity}個{stale}) ===")
        for group, entries in _by_group(report.entries):
            quantity = sum(e.quantity for e in entries)
            click.echo(f"  [{group}] {len(entries)}行 / {quantity}個")
            for entry in entries:
                elapsed = f"{entry.elapsed:>3d}日" if entry.elapsed is not None else " -- "
                mark = "  ⚠️" if entry.elapsed is not None and entry.elapsed > stale_days else ""
                click.echo(
                    f"    {elapsed} 行{entry.row_number} {entry.since or '日付なし'} "
                    f"| {entry.product_name[:30]} {entry.quantity}個{mark}"
                )


def _by_group(entries: list[StageEntry]) -> list[tuple[str, list[StageEntry]]]:
    grouped: dict[str, list[StageEntry]] = {}
    for entry in entries:
        grouped.setdefault(entry.group, []).append(entry)
    return sorted(grouped.items(), key=lambda kv: -max(e.elapsed or -1 for e in kv[1]))
