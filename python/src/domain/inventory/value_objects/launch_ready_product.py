from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

ASIN_COLUMN = "ASIN"
PRODUCT_NAME_COLUMN = "商品名"
PURCHASE_COUNT_COLUMN = "仕入回数"
RECEIVED_DATE_COLUMN = "受領日"
INVENTORY_COLUMN = "在庫数"
FIRST_PURCHASE_COUNT = 1


@dataclass(frozen=True)
class LaunchReadyProduct:
    asin: str
    product_name: str
    received_date: str
    inventory_quantity: int

    @property
    def product_url(self) -> str:
        return f"https://www.amazon.co.jp/dp/{self.asin}"


def _text(row: Mapping[str, Any], column: str) -> str:
    return str(row.get(column) or "").strip()


def _to_int(value: Any) -> int | None:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return None


def _is_first_purchase(row: Mapping[str, Any]) -> bool:
    return _to_int(row.get(PURCHASE_COUNT_COLUMN)) == FIRST_PURCHASE_COUNT


def collect_launch_ready_products(
    rows: Sequence[Mapping[str, Any]], *, notified_asins: set[str]
) -> list[LaunchReadyProduct]:
    products: list[LaunchReadyProduct] = []
    seen: set[str] = set()

    for row in rows:
        asin = _text(row, ASIN_COLUMN)
        if not asin or asin in notified_asins or asin in seen:
            continue
        if not _is_first_purchase(row):
            continue
        received_date = _text(row, RECEIVED_DATE_COLUMN)
        if not received_date:
            continue

        seen.add(asin)
        products.append(
            LaunchReadyProduct(
                asin=asin,
                product_name=_text(row, PRODUCT_NAME_COLUMN),
                received_date=received_date,
                inventory_quantity=_to_int(row.get(INVENTORY_COLUMN)) or 0,
            )
        )

    return products
