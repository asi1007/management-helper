import pytest

from usecases.update_inventory_estimate_from_stock import (
    StockUnavailableError,
    _load_asin_to_available_stock,
)


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
    def __init__(self, spreadsheet: FakeSpreadsheet) -> None:
        self._spreadsheet = spreadsheet

    def open_spreadsheet(self, sheet_id: str) -> FakeSpreadsheet:
        return self._spreadsheet


class UnavailableRepository:
    def open_spreadsheet(self, sheet_id: str) -> FakeSpreadsheet:
        raise RuntimeError("APIError: [503]: The service is currently unavailable.")


HEADERS = [
    "ASIN",
    "販売可能\n(fulfillableQuantity)",
    "受領中\n(inboundReceivingQuantity)",
    "転送中\n(pendingTransshipmentQuantity)",
    "処理中\n(fcProcessingQuantity)",
]


def _repo(values: list[list[str]]) -> FakeRepository:
    return FakeRepository(FakeSpreadsheet({"stock": FakeWorksheet(values)}))


def test_returns_totals_per_asin():
    repo = _repo(
        [
            HEADERS,
            ["B001", "83", "0", "0", "0"],
            ["B002", "1,445", "0", "0", "0"],
            ["B001", "17", "0", "0", "0"],
        ]
    )

    assert _load_asin_to_available_stock(repo, "sheet") == {"B001": 100, "B002": 1445}


def test_raises_when_spreadsheet_unavailable():
    with pytest.raises(StockUnavailableError):
        _load_asin_to_available_stock(UnavailableRepository(), "sheet")


def test_raises_when_stock_worksheet_missing():
    repo = FakeRepository(FakeSpreadsheet({}))

    with pytest.raises(StockUnavailableError):
        _load_asin_to_available_stock(repo, "sheet")


def test_raises_when_stock_sheet_empty():
    with pytest.raises(StockUnavailableError):
        _load_asin_to_available_stock(_repo([]), "sheet")


def test_raises_when_required_columns_missing():
    with pytest.raises(StockUnavailableError):
        _load_asin_to_available_stock(_repo([["ASIN", "予約済み"], ["B001", "1"]]), "sheet")


def test_raises_when_no_asin_rows():
    with pytest.raises(StockUnavailableError):
        _load_asin_to_available_stock(_repo([HEADERS]), "sheet")
