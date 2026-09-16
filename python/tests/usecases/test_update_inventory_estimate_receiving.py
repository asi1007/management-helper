from __future__ import annotations

from types import SimpleNamespace

from infrastructure.spreadsheet.base_row import BaseRow
from usecases.update_inventory_estimate_from_stock import update_inventory_estimate

HEADERS = ["ASIN", "状態", "購入数", "在庫数", "受領開始日"]
CONFIG = SimpleNamespace(
    sheet_id="sheet", purchase_sheet_name="仕入管理",
    todoist_api_token="t", todoist_project="INBOX",
)


def _row(
    row_number: int, asin: str, status: str, purchase: str,
    inventory: str = "", receiving_started: str = "",
) -> BaseRow:
    return BaseRow(
        [asin, status, purchase, inventory, receiving_started], HEADERS.index, row_number
    )


class FakeWorksheet:
    def __init__(self) -> None:
        self.updates: list[dict] = []

    def batch_update(self, updates, value_input_option="RAW") -> None:
        self.updates.extend(updates)


class FakePurchaseSheet:
    def __init__(self, rows: list[BaseRow]) -> None:
        self.all_data = rows
        self.data = rows
        self._worksheet = FakeWorksheet()

    def filter(self, column_name: str, values: list) -> list[BaseRow]:
        self.data = [r for r in self.all_data if r.get(column_name) in values]
        return self.data

    def _get_column_index_by_name(self, column_name: str) -> int:
        return HEADERS.index(column_name)


class SpyNotifier:
    def __init__(self) -> None:
        self.calls: list[list] = []

    def notify(self, shortfalls, due_date) -> None:
        self.calls.append(shortfalls)


def _run(mocker, rows: list[BaseRow], stock: dict[str, int]) -> SpyNotifier:
    mocker.patch(
        "usecases.update_inventory_estimate_from_stock.PurchaseSheet",
        return_value=FakePurchaseSheet(rows),
    )
    mocker.patch(
        "usecases.update_inventory_estimate_from_stock._load_asin_to_available_stock",
        return_value=stock,
    )
    notifier = SpyNotifier()
    update_inventory_estimate(CONFIG, object(), notifier=notifier)
    return notifier


def test_a_row_being_received_absorbs_the_stock_that_arrived_early(mocker) -> None:
    # 2026-09-12 の B0FWJZXCY8。FCは受領を始めているが受領率90%未満で「発送済み」のまま
    rows = [
        _row(102, "B0FWJZXCY8", "在庫あり", "2000", "2000"),
        _row(142, "B0FWJZXCY8", "在庫あり", "1561", "1561"),
        _row(191, "B0FWJZXCY8", "発送済み", "1514", "", "2026/09/12"),
    ]

    notifier = _run(mocker, rows, {"B0FWJZXCY8": 4682})

    assert notifier.calls == [[]]


def test_a_row_that_has_not_started_receiving_is_not_a_capacity(mocker) -> None:
    # まだ受領が始まっていない行まで受け皿に数えると、行が消えたことに気づけなくなる
    rows = [
        _row(102, "B001", "在庫あり", "2000", "2000"),
        _row(191, "B001", "発送済み", "1514"),
    ]

    notifier = _run(mocker, rows, {"B001": 4682})

    assert [(s.asin, s.quantity) for s in notifier.calls[0]] == [("B001", 2682)]


def test_a_received_row_is_not_counted_twice(mocker) -> None:
    # 受領が終わって在庫数が入った行は配分で数えるので、購入数を重ねてはいけない
    rows = [_row(102, "B001", "在庫あり", "2000", "2000", "2026/09/10")]

    notifier = _run(mocker, rows, {"B001": 3000})

    assert [(s.asin, s.quantity) for s in notifier.calls[0]] == [("B001", 1000)]


def test_an_asin_without_any_row_is_still_reported(mocker) -> None:
    rows = [_row(102, "B001", "在庫あり", "2000", "2000")]

    notifier = _run(mocker, rows, {"B001": 2000, "B098J9VPW3": 40})

    assert [(s.asin, s.quantity) for s in notifier.calls[0]] == [("B098J9VPW3", 40)]


def test_a_handful_of_units_without_any_row_is_not_reported(mocker) -> None:
    rows = [_row(102, "B001", "在庫あり", "2000", "2000")]

    notifier = _run(mocker, rows, {"B001": 2000, "B098J9VPW3": 5})

    assert notifier.calls == [[]]


def test_a_malformed_purchase_quantity_does_not_break_the_run(mocker) -> None:
    rows = [
        _row(102, "B001", "在庫あり", "2,000", "2000"),
        _row(191, "B001", "発送済み", "", "", "2026/09/12"),
        _row(192, "B001", "発送済み", "1,514", "", "2026/09/12"),
    ]

    notifier = _run(mocker, rows, {"B001": 3514})

    assert notifier.calls == [[]]
