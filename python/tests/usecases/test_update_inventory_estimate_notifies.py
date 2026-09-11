from __future__ import annotations

from types import SimpleNamespace

from infrastructure.spreadsheet.base_row import BaseRow
from usecases.update_inventory_estimate_from_stock import update_inventory_estimate

HEADERS = ["ASIN", "状態", "購入数", "在庫数"]
CONFIG = SimpleNamespace(
    sheet_id="sheet", purchase_sheet_name="仕入管理",
    todoist_api_token="t", todoist_project="INBOX",
)


def _row(row_number: int, asin: str, purchase: str, inventory: str) -> BaseRow:
    return BaseRow([asin, "在庫あり", purchase, inventory], HEADERS.index, row_number)


class FakeWorksheet:
    def batch_update(self, updates, value_input_option="RAW") -> None:
        pass


class FakePurchaseSheet:
    def __init__(self, rows: list[BaseRow]) -> None:
        self.all_data = rows
        self.data = rows
        self._worksheet = FakeWorksheet()

    def filter(self, column_name: str, values: list) -> list[BaseRow]:
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


def test_notifies_when_stock_does_not_fit_in_the_rows(mocker) -> None:
    notifier = _run(mocker, [_row(10, "B001", "700", "700")], {"B001": 1000})

    assert [(s.asin, s.quantity) for s in notifier.calls[0]] == [("B001", 300)]


def test_notifies_for_an_asin_that_has_no_row(mocker) -> None:
    notifier = _run(mocker, [_row(10, "B001", "700", "700")], {"B001": 700, "B002": 40})

    assert [(s.asin, s.quantity) for s in notifier.calls[0]] == [("B002", 40)]


def test_does_not_notify_when_every_unit_is_assigned(mocker) -> None:
    notifier = _run(mocker, [_row(10, "B001", "700", "700")], {"B001": 700})

    assert notifier.calls == [[]]
