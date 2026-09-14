from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StockShortfall:
    asin: str
    fba_quantity: int
    capacity_quantity: int

    @property
    def quantity(self) -> int:
        return self.fba_quantity - self.capacity_quantity

    @property
    def product_url(self) -> str:
        return f"https://www.amazon.co.jp/dp/{self.asin}"


def collect_shortfalls(
    asin_to_stock: dict[str, int], asin_to_capacity: dict[str, int]
) -> list[StockShortfall]:
    shortfalls = [
        StockShortfall(
            asin=asin, fba_quantity=stock, capacity_quantity=asin_to_capacity.get(asin, 0)
        )
        for asin, stock in asin_to_stock.items()
        if stock > 0 and stock > asin_to_capacity.get(asin, 0)
    ]
    return sorted(shortfalls, key=lambda s: -s.quantity)
