from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import click

from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet
from shared.config import AppConfig

# 「仕入回数」列は CD 列。初回仕入れ＝まだ一度も納品していない新商品
FIRST_PURCHASE_COUNT = 1
PURCHASE_COUNT_HEADER = "仕入回数"
TARGET_STATUS = "梱包依頼必要"
UNCATEGORIZED = "未分類"


@dataclass(frozen=True)
class NewProductRow:
    row_number: int
    asin: str
    product_name: str
    quantity: int
    category: str
    sku: str
    fnsku: str
    purchased_on: str
    arrived_on: str

    @classmethod
    def from_row(cls, row: Any) -> "NewProductRow":
        return cls(
            row_number=row.row_number,
            asin=str(row.get("ASIN") or "").strip(),
            product_name=str(row.get("商品名") or "").strip(),
            quantity=_to_int(row.get("購入数")),
            category=str(row.get("納品分類") or "").strip() or UNCATEGORIZED,
            sku=str(row.get("SKU") or "").strip(),
            fnsku=str(row.get("FNSKU") or "").strip(),
            purchased_on=str(row.get("購入日") or "").strip(),
            arrived_on=str(row.get("到着日") or "").strip(),
        )

    @property
    def has_identifiers(self) -> bool:
        return bool(self.sku and self.fnsku)


@dataclass
class CategorySummary:
    category: str
    rows: list[NewProductRow] = field(default_factory=list)

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def total_quantity(self) -> int:
        return sum(r.quantity for r in self.rows)

    @property
    def missing_identifier_rows(self) -> list[int]:
        return [r.row_number for r in self.rows if not r.has_identifiers]


def _to_int(value: Any) -> int:
    try:
        return int(str(value or "0").strip() or 0)
    except ValueError:
        return 0


def _is_first_purchase(row: Any) -> bool:
    raw = str(row.get(PURCHASE_COUNT_HEADER) or "").strip()
    if not raw.isdigit():
        return False
    return int(raw) == FIRST_PURCHASE_COUNT


def select_new_product_rows(rows: list[Any]) -> list[Any]:
    """初回仕入れ（仕入回数=1）の行だけを行番号順で返す"""
    selected = [
        r for r in rows
        if str(r.get("ASIN") or "").strip() and _is_first_purchase(r)
    ]
    selected.sort(key=lambda r: r.row_number)
    return selected


def summarize_by_category(rows: list[Any]) -> dict[str, CategorySummary]:
    summaries: dict[str, CategorySummary] = {}
    for row in rows:
        entry = NewProductRow.from_row(row)
        summaries.setdefault(entry.category, CategorySummary(category=entry.category)).rows.append(entry)
    return summaries


def list_new_product_shipments(
    config: AppConfig, repo: BaseSheetsRepository
) -> dict[str, CategorySummary]:
    """梱包依頼必要かつ初回仕入れの行を納品分類ごとに一覧する。書き換えはしない。"""
    sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    sheet.filter("状態", [TARGET_STATUS])
    summaries = summarize_by_category(select_new_product_rows(sheet.data))
    _print_summaries(summaries)
    return summaries


def _print_summaries(summaries: dict[str, CategorySummary]) -> None:
    if not summaries:
        click.echo("初回仕入れで梱包依頼が必要な行はありません")
        return
    total_rows = sum(s.row_count for s in summaries.values())
    total_quantity = sum(s.total_quantity for s in summaries.values())
    click.echo(f"新商品（仕入回数{FIRST_PURCHASE_COUNT}）で梱包依頼必要: {total_rows}行 / {total_quantity}個\n")
    for category, summary in sorted(summaries.items()):
        click.echo(f"=== {category} ({summary.row_count}行 / {summary.total_quantity}個) ===")
        for entry in summary.rows:
            mark = "" if entry.has_identifiers else "  ⚠️SKU/FNSKU欠"
            click.echo(
                f"  行{entry.row_number} 購入{entry.purchased_on:6s} 到着{entry.arrived_on:6s}"
                f" | {entry.product_name[:34]:34s} {entry.quantity:>5}個{mark}"
            )
        if summary.missing_identifier_rows:
            click.echo(f"  ⚠️ SKU/FNSKU未設定: 行{summary.missing_identifier_rows}")
    click.echo("\n出すときは --categories に上の分類を渡して batch-labels を実行する（空輸は --air）")
