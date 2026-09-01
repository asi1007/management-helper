from types import SimpleNamespace

import pytest

from infrastructure.spreadsheet.base_row import BaseRow
from usecases.archive_out_of_stock import (
    MAX_ARCHIVE_ROWS,
    TooManyArchiveRowsError,
    archive_out_of_stock,
)

HEADERS = ["備考", "行番号", "ASIN", "状態"]


def _row(row_number: int, status: str) -> BaseRow:
    return BaseRow(["", str(row_number), "B001", status], HEADERS.index, row_number)


class FakeSpreadsheetBody:
    def __init__(self) -> None:
        self.requests: list[dict] = []

    def batch_update(self, body: dict) -> None:
        self.requests.extend(body["requests"])


class FakePurchaseWorksheet:
    def __init__(self) -> None:
        self.id = 1
        self.spreadsheet = FakeSpreadsheetBody()


class FakeArchiveWorksheet:
    def __init__(self) -> None:
        self.appended: list[list] = []

    def append_rows(self, rows: list[list], value_input_option: str = "RAW") -> None:
        self.appended.extend(rows)


class FakeSpreadsheet:
    def __init__(self, archive: FakeArchiveWorksheet) -> None:
        self._archive = archive

    def worksheet(self, title: str) -> FakeArchiveWorksheet:
        return self._archive


class FakeRepository:
    def __init__(self, archive: FakeArchiveWorksheet) -> None:
        self._spreadsheet = FakeSpreadsheet(archive)

    def open_spreadsheet(self, sheet_id: str) -> FakeSpreadsheet:
        return self._spreadsheet


class FakePurchaseSheet:
    def __init__(self, rows: list[BaseRow]) -> None:
        self.all_data = rows
        self._worksheet = FakePurchaseWorksheet()


CONFIG = SimpleNamespace(sheet_id="sheet", purchase_sheet_name="仕入管理")


def _run(mocker, rows: list[BaseRow]) -> tuple[FakeArchiveWorksheet, FakePurchaseSheet]:
    sheet = FakePurchaseSheet(rows)
    archive = FakeArchiveWorksheet()
    mocker.patch("usecases.archive_out_of_stock.PurchaseSheet", return_value=sheet)
    return archive, sheet


def test_archives_rows_within_limit(mocker):
    rows = [_row(n, "在庫なし") for n in range(6, 6 + MAX_ARCHIVE_ROWS)]
    archive, sheet = _run(mocker, rows)

    archive_out_of_stock(CONFIG, FakeRepository(archive))

    assert len(archive.appended) == MAX_ARCHIVE_ROWS
    assert len(sheet._worksheet.spreadsheet.requests) == MAX_ARCHIVE_ROWS


def test_aborts_without_writing_when_over_limit(mocker):
    rows = [_row(n, "在庫なし") for n in range(6, 6 + MAX_ARCHIVE_ROWS + 1)]
    archive, sheet = _run(mocker, rows)

    with pytest.raises(TooManyArchiveRowsError):
        archive_out_of_stock(CONFIG, FakeRepository(archive))

    assert archive.appended == []
    assert sheet._worksheet.spreadsheet.requests == []
