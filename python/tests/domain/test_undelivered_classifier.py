from __future__ import annotations

from datetime import date

from domain.shipment.undelivered_classifier import (
    InquiryVerdict,
    UndeliveredShipment,
    classify_shipment,
)


def _shipment(
    *,
    shipped_on: date = date(2026, 7, 1),
    status: str = "SHIPPED",
    qty_shipped: int = 1000,
    qty_received: int = 0,
    tracking: str = "",
) -> UndeliveredShipment:
    return UndeliveredShipment(
        shipment_confirmation_id="FBA15GF2X4FF",
        plan_alias="07/07ノーマル",
        shipped_on=shipped_on,
        status=status,
        quantity_shipped=qty_shipped,
        quantity_received=qty_received,
        tracking_number=tracking,
        rows=[],
    )


class TestClassifyShipment:
    def test_CLOSEDなら受領済みとみなし問い合わせ不要(self) -> None:
        shipment = _shipment(status="CLOSED", qty_shipped=1000, qty_received=0)
        assert classify_shipment(shipment, today=date(2026, 8, 10)) == InquiryVerdict.ALREADY_RECEIVED

    def test_受領率9割以上なら受領済みとみなす(self) -> None:
        shipment = _shipment(qty_shipped=1000, qty_received=950)
        assert classify_shipment(shipment, today=date(2026, 8, 10)) == InquiryVerdict.ALREADY_RECEIVED

    def test_閾値内なら輸送中として様子見(self) -> None:
        shipment = _shipment(shipped_on=date(2026, 7, 29))
        assert classify_shipment(shipment, today=date(2026, 8, 10)) == InquiryVerdict.IN_TRANSIT

    def test_閾値超で未受領なら問い合わせ対象(self) -> None:
        shipment = _shipment(shipped_on=date(2026, 7, 1))
        assert classify_shipment(shipment, today=date(2026, 8, 10)) == InquiryVerdict.NEEDS_INQUIRY

    def test_一部だけ受領していても閾値超なら問い合わせ対象(self) -> None:
        shipment = _shipment(shipped_on=date(2026, 7, 1), qty_shipped=1000, qty_received=300)
        assert classify_shipment(shipment, today=date(2026, 8, 10)) == InquiryVerdict.NEEDS_INQUIRY

    def test_閾値は上書きできる(self) -> None:
        shipment = _shipment(shipped_on=date(2026, 8, 1))
        assert classify_shipment(shipment, today=date(2026, 8, 10), threshold_days=7) == InquiryVerdict.NEEDS_INQUIRY

    def test_発送日が未来ならデータ異常として扱う(self) -> None:
        shipment = _shipment(shipped_on=date(2026, 9, 1))
        assert classify_shipment(shipment, today=date(2026, 8, 10)) == InquiryVerdict.INVALID_SHIP_DATE

    def test_発送日が無ければデータ異常として扱う(self) -> None:
        shipment = UndeliveredShipment(
            shipment_confirmation_id="FBA15G000TTF",
            plan_alias="",
            shipped_on=None,
            status="SHIPPED",
            quantity_shipped=300,
            quantity_received=0,
            tracking_number="",
            rows=[],
        )
        assert classify_shipment(shipment, today=date(2026, 8, 10)) == InquiryVerdict.INVALID_SHIP_DATE


class TestElapsedDays:
    def test_経過日数を返す(self) -> None:
        shipment = _shipment(shipped_on=date(2026, 7, 1))
        assert shipment.elapsed_days(date(2026, 8, 10)) == 40

    def test_発送日が無ければNone(self) -> None:
        shipment = UndeliveredShipment(
            shipment_confirmation_id="X", plan_alias="", shipped_on=None, status="",
            quantity_shipped=0, quantity_received=0, tracking_number="", rows=[],
        )
        assert shipment.elapsed_days(date(2026, 8, 10)) is None
