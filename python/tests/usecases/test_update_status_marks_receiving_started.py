from __future__ import annotations

from infrastructure.spreadsheet.base_row import BaseRow
from usecases import update_status_estimate as mod
from usecases.update_status_estimate import _should_mark_receiving_started

HEADERS = ["ASIN", "状態", "購入数", "在庫数", "受領開始日", "受領日", "SKU", "納品プラン"]


def test_marks_the_day_receiving_started() -> None:
    assert _should_mark_receiving_started(qty_received=1228, current_value="") is True


def test_does_not_mark_before_anything_is_received() -> None:
    assert _should_mark_receiving_started(qty_received=0, current_value="") is False


def test_keeps_the_first_day_it_was_recorded() -> None:
    # 「開始日」なので上書きしない。いつから受領が始まったかが失われる
    assert _should_mark_receiving_started(qty_received=4993, current_value="2026/09/12") is False


class FakeConfig:
    sheet_id = "SID"
    purchase_sheet_name = "仕入管理"


class FakeCreator:
    def __init__(self, shipped: int, received: int) -> None:
        self._shipped = shipped
        self._received = received

    def get_shipment_status(self, shipment_id: str) -> str:
        return "RECEIVING"

    def get_shipment_items(self, shipment_id: str) -> list[dict]:
        return [
            {
                "SellerSKU": "OS-LI7Z-UMQ7",
                "QuantityShipped": self._shipped,
                "QuantityReceived": self._received,
            }
        ]


class FakeSheet:
    def __init__(self, rows: list[BaseRow]) -> None:
        self.all_data = rows
        self.written: list[tuple[int, int, object]] = []

    def _get_column_index_by_name(self, column_name: str) -> int:
        return HEADERS.index(column_name)

    def write_cell(self, row_num: int, column_num: int, value: object) -> None:
        self.written.append((row_num, column_num, value))


def _row(row_number: int, receiving_started: str = "") -> BaseRow:
    return BaseRow(
        ["B0FWJZXCY8", "発送済み", "1514", "", receiving_started, "", "OS-LI7Z-UMQ7", "FBA15GBW843C"],
        HEADERS.index,
        row_number,
    )


def _run(monkeypatch, rows: list[BaseRow], shipped: int, received: int) -> FakeSheet:
    sheet = FakeSheet(rows)
    monkeypatch.setattr(mod, "get_auth_token", lambda *a, **k: "tok")
    monkeypatch.setattr(mod, "InboundPlanCreator", lambda tok: FakeCreator(shipped, received))
    monkeypatch.setattr(mod, "fill_sku_fnsku_from_shipment", lambda config, repo: None)
    monkeypatch.setattr(mod, "PurchaseSheet", lambda *a, **k: sheet)
    mod.update_status_estimate(config=FakeConfig(), repo=object())
    return sheet


def test_writes_the_receiving_started_date_while_still_below_the_threshold(monkeypatch) -> None:
    # 受領率81%。在庫数はまだ入らないが、FBAには1228個が載っている
    sheet = _run(monkeypatch, [_row(191)], shipped=1514, received=1228)

    started_col = HEADERS.index("受領開始日") + 1
    assert [(r, c) for r, c, _ in sheet.written] == [(191, started_col)]


def test_does_not_touch_a_row_that_already_has_the_date(monkeypatch) -> None:
    sheet = _run(monkeypatch, [_row(191, "2026/09/12")], shipped=1514, received=1228)

    assert sheet.written == []


def test_still_writes_the_inventory_once_receiving_completes(monkeypatch) -> None:
    sheet = _run(monkeypatch, [_row(191, "2026/09/12")], shipped=1514, received=1500)

    inv_col = HEADERS.index("在庫数") + 1
    assert (191, inv_col, 1500) in sheet.written
