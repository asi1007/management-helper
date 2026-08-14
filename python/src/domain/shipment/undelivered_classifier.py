from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any

DEFAULT_THRESHOLD_DAYS = 21
RECEIVED_RATIO = 0.9


class InquiryVerdict(Enum):
    ALREADY_RECEIVED = "受領済み"
    IN_TRANSIT = "輸送中"
    NEEDS_INQUIRY = "要問い合わせ"
    INVALID_SHIP_DATE = "発送日が不正"


@dataclass(frozen=True)
class UndeliveredShipment:
    shipment_confirmation_id: str
    plan_alias: str
    shipped_on: date | None
    status: str
    quantity_shipped: int
    quantity_received: int
    tracking_number: str
    product_names: list[str] = field(default_factory=list)
    rows: list[Any] = field(default_factory=list)

    def elapsed_days(self, today: date) -> int | None:
        if self.shipped_on is None:
            return None
        return (today - self.shipped_on).days


def classify_shipment(
    shipment: UndeliveredShipment,
    *,
    today: date,
    threshold_days: int = DEFAULT_THRESHOLD_DAYS,
) -> InquiryVerdict:
    if _is_received(shipment):
        return InquiryVerdict.ALREADY_RECEIVED
    elapsed = shipment.elapsed_days(today)
    if elapsed is None or elapsed < 0:
        return InquiryVerdict.INVALID_SHIP_DATE
    if elapsed < threshold_days:
        return InquiryVerdict.IN_TRANSIT
    return InquiryVerdict.NEEDS_INQUIRY


def _is_received(shipment: UndeliveredShipment) -> bool:
    if shipment.status == "CLOSED" and shipment.quantity_shipped > 0:
        return True
    if shipment.quantity_shipped <= 0:
        return False
    return shipment.quantity_received / shipment.quantity_shipped >= RECEIVED_RATIO
