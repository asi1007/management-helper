from __future__ import annotations

from dataclasses import dataclass


# 顧客返品が再入庫すると、売り切って受け皿の無くなった行のASINに数個だけFBA在庫が戻る。
# 本来は返品数を受け皿として持たせるべきだが、この規模の差は運用上の打ち手が無いので
# 通知しないことにした（= 返品由来かどうかの区別は諦めている）。2026-09-16
IGNORED_QUANTITY = 5


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
        if stock > 0 and stock - asin_to_capacity.get(asin, 0) > IGNORED_QUANTITY
    ]
    return sorted(shortfalls, key=lambda s: -s.quantity)
