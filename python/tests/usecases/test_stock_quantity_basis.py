from __future__ import annotations

import pytest

from usecases.update_inventory_estimate_from_stock import (
    StockUnavailableError,
    _load_asin_to_available_stock,
)

HEADERS = [
    "ASIN",
    "販売可能\n(fulfillableQuantity)",
    "受領中\n(inboundReceivingQuantity)",
    "予約済合計\n(totalReservedQuantity)",
    "注文確保\n(pendingCustomerOrderQuantity)",
    "転送中\n(pendingTransshipmentQuantity)",
    "処理中\n(fcProcessingQuantity)",
]


class FakeWorksheet:
    def __init__(self, values: list[list[str]]) -> None:
        self._values = values

    def get_all_values(self) -> list[list[str]]:
        return self._values


class FakeSpreadsheet:
    def __init__(self, sheets: dict[str, FakeWorksheet]) -> None:
        self._sheets = sheets

    def worksheet(self, title: str) -> FakeWorksheet:
        if title not in self._sheets:
            raise RuntimeError(f"worksheet not found: {title}")
        return self._sheets[title]


class FakeRepository:
    def __init__(self, values: list[list[str]]) -> None:
        self._spreadsheet = FakeSpreadsheet({"stock": FakeWorksheet(values)})

    def open_spreadsheet(self, sheet_id: str) -> FakeSpreadsheet:
        return self._spreadsheet


def test_counts_receiving_quantity_as_stock() -> None:
    repo = FakeRepository([HEADERS, ["B0DHTN6C5P", "0", "2,936", "0", "0", "0", "0"]])

    assert _load_asin_to_available_stock(repo, "sheet") == {"B0DHTN6C5P": 2936}


def test_counts_transshipment_and_processing_as_stock() -> None:
    repo = FakeRepository([HEADERS, ["B001", "500", "0", "12", "0", "7", "5"]])

    assert _load_asin_to_available_stock(repo, "sheet") == {"B001": 512}


def test_excludes_quantity_reserved_for_customer_orders() -> None:
    # 注文確保はすでに客の注文が付いており、出荷されて手元から出ていく
    repo = FakeRepository([HEADERS, ["B001", "500", "0", "30", "30", "0", "0"]])

    assert _load_asin_to_available_stock(repo, "sheet") == {"B001": 500}


def test_does_not_double_count_the_reserved_total() -> None:
    # 予約済合計 = 注文確保 + 転送中 + 処理中 なので合計列は使わない
    repo = FakeRepository([HEADERS, ["B001", "100", "10", "20", "8", "7", "5"]])

    assert _load_asin_to_available_stock(repo, "sheet") == {"B001": 122}


def test_raises_when_a_quantity_column_is_missing() -> None:
    repo = FakeRepository([HEADERS[:3], ["B001", "500", "0"]])

    with pytest.raises(StockUnavailableError):
        _load_asin_to_available_stock(repo, "sheet")


def test_raises_when_every_asin_has_no_stock_at_all() -> None:
    repo = FakeRepository([HEADERS, ["B001", "0", "0", "0", "0", "0", "0"]])

    with pytest.raises(StockUnavailableError):
        _load_asin_to_available_stock(repo, "sheet")
