from __future__ import annotations

from datetime import date

from domain.shipment.inquiry_message_builder import build_inquiry_message
from domain.shipment.undelivered_classifier import UndeliveredShipment


def _shipment(
    shipment_id: str,
    alias: str,
    shipped_on: date,
    tracking: str = "",
    received: int = 0,
    product_names: list[str] | None = None,
) -> UndeliveredShipment:
    return UndeliveredShipment(
        shipment_confirmation_id=shipment_id,
        plan_alias=alias,
        shipped_on=shipped_on,
        status="SHIPPED",
        quantity_shipped=1000,
        quantity_received=received,
        tracking_number=tracking,
        product_names=product_names or [],
        rows=[],
    )


class TestBuildInquiryMessage:
    def test_宛先タグと納品番号と経過日数を含める(self) -> None:
        shipments = [_shipment("FBA15G6CY59F", "01/21ノーマル", date(2026, 2, 5))]
        message = build_inquiry_message(shipments, today=date(2026, 8, 10), to_account_id="986396")

        assert message.startswith("[To:986396]徐雪蘭さん")
        assert "FBA15G6CY59F" in message
        assert "01/21ノーマル" in message
        assert "186日" in message

    def test_複数件を経過日数の長い順に並べる(self) -> None:
        shipments = [
            _shipment("FBA-NEW", "07/07ノーマル", date(2026, 7, 20)),
            _shipment("FBA-OLD", "01/21ノーマル", date(2026, 2, 5)),
        ]
        message = build_inquiry_message(shipments, today=date(2026, 8, 10), to_account_id="986396")

        assert message.index("FBA-OLD") < message.index("FBA-NEW")

    def test_追跡番号があれば併記する(self) -> None:
        shipments = [_shipment("FBA-X", "07/07ノーマル", date(2026, 6, 1), tracking="SF1234567890")]
        message = build_inquiry_message(shipments, today=date(2026, 8, 10), to_account_id="986396")

        assert "SF1234567890" in message

    def test_一部受領があれば数量を併記する(self) -> None:
        shipments = [_shipment("FBA-Y", "07/07ノーマル", date(2026, 6, 1), received=300)]
        message = build_inquiry_message(shipments, today=date(2026, 8, 10), to_account_id="986396")

        assert "300" in message and "1000" in message

    def test_宛先IDが無ければ宛先タグを省く(self) -> None:
        shipments = [_shipment("FBA-Z", "07/07ノーマル", date(2026, 6, 1))]
        message = build_inquiry_message(shipments, today=date(2026, 8, 10), to_account_id="")

        assert not message.startswith("[To:")

    def test_対象が無ければ空文字(self) -> None:
        assert build_inquiry_message([], today=date(2026, 8, 10), to_account_id="986396") == ""

    def test_内部プレースホルダのプラン別名は出力しない(self) -> None:
        shipments = [_shipment("FBA-P", "__PENDING_X0019JUH6D__", date(2026, 6, 29))]
        message = build_inquiry_message(shipments, today=date(2026, 8, 10), to_account_id="986396")

        assert "__PENDING" not in message
        assert "指示書" not in message

    def test_商品名を併記する(self) -> None:
        shipments = [_shipment("FBA-Q", "07/07ノーマル", date(2026, 6, 1), product_names=["A4額縁", "巻き尺"])]
        message = build_inquiry_message(shipments, today=date(2026, 8, 10), to_account_id="986396")

        assert "A4額縁" in message and "巻き尺" in message

    def test_商品名が多いときは3件までにして残数を示す(self) -> None:
        names = [f"商品{i}" for i in range(1, 8)]
        shipments = [_shipment("FBA-R", "07/07ノーマル", date(2026, 6, 1), product_names=names)]
        message = build_inquiry_message(shipments, today=date(2026, 8, 10), to_account_id="986396")

        assert "商品1" in message and "商品3" in message
        assert "商品4" not in message
        assert "他4件" in message
