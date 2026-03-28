from __future__ import annotations


class LabelItem:
    def __init__(self, sku: str, quantity: int) -> None:
        self.sku = str(sku or "").strip()
        self.quantity = int(quantity) if quantity else 0
        if not self.sku:
            raise ValueError("SKUが空です")
        if self.quantity <= 0:
            raise ValueError(f"数量が不正です: {quantity}")

    def to_msku_quantity(self) -> dict[str, str | int]:
        return {"msku": self.sku, "quantity": self.quantity}
