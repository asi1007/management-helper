from __future__ import annotations

from types import SimpleNamespace

from infrastructure.spreadsheet.base_row import BaseRow
from usecases.update_inventory_estimate_from_stock import update_inventory_estimate

HEADERS = ["ASIN", "状態", "購入数", "在庫数"]
CONFIG = SimpleNamespace(sheet_id="sheet", purchase_sheet_name="仕入管理")


def _row(row_number: int, asin: str, purchase: str, inventory: str) -> BaseRow:
    return BaseRow([asin, "在庫あり", purchase, inventory], HEADERS.index, row_number)


class FakeWorksheet:
    def __init__(self) -> None:
        self.updates: list[dict] = []

    def batch_update(self, updates: list[dict], value_input_option: str = "RAW") -> None:
        self.updates.extend(updates)


class FakePurchaseSheet:
    def __init__(self, rows: list[BaseRow]) -> None:
        self.all_data = rows
        self.data = rows
        self._worksheet = FakeWorksheet()

    def filter(self, column_name: str, values: list) -> list[BaseRow]:
        return self.data

    def _get_column_index_by_name(self, column_name: str) -> int:
        return HEADERS.index(column_name)


def _run(mocker, rows: list[BaseRow], stock: dict[str, int]) -> FakeWorksheet:
    sheet = FakePurchaseSheet(rows)
    mocker.patch(
        "usecases.update_inventory_estimate_from_stock.PurchaseSheet",
        return_value=sheet,
    )
    mocker.patch(
        "usecases.update_inventory_estimate_from_stock._load_asin_to_available_stock",
        return_value=stock,
    )
    update_inventory_estimate(CONFIG, object())
    return sheet._worksheet


def test_does_not_write_zero_for_asin_missing_from_stock(mocker) -> None:
    rows = [_row(10, "B0MISSING", "1500", "1200")]

    worksheet = _run(mocker, rows, {"B0OTHER": 500})

    assert worksheet.updates == []


def test_still_writes_zero_when_stock_reports_the_asin_as_empty(mocker) -> None:
    rows = [_row(10, "B0SOLDOUT", "1500", "1200")]

    worksheet = _run(mocker, rows, {"B0SOLDOUT": 0, "B0OTHER": 500})

    assert worksheet.updates == [{"range": "D10", "values": [[0]]}]
