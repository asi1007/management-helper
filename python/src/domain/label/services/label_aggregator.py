from __future__ import annotations
from typing import Protocol
from domain.label.entities.label_item import LabelItem


class RowLike(Protocol):
    def get(self, column_name: str) -> str: ...


class LabelAggregator:
    def aggregate(self, rows: list[RowLike]) -> list[LabelItem]:
        sku_totals: dict[str, int] = {}
        for row in rows or []:
            sku = str(row.get("SKU") or "").strip()
            raw_qty = row.get("購入数")
            quantity = int(raw_qty) if raw_qty else 0
            if not sku or quantity <= 0:
                continue
            sku_totals[sku] = sku_totals.get(sku, 0) + quantity
        items = [LabelItem(sku=sku, quantity=qty) for sku, qty in sku_totals.items()]
        if not items:
            raise ValueError("有効なSKUがありません")
        return items
