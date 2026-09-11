from __future__ import annotations

from datetime import date

from usecases.archive_out_of_stock import archive_out_of_stock

HEADER = ["ASIN", "状態", "在庫数", "受領日"]
RECEIVED_2026_08_14 = 46248
RECEIVED_2026_09_30 = 46295  # 前月末ちょうど
RECEIVED_2026_10_01 = 46296  # 当月


class FakeParentSpreadsheet:
    def __init__(self) -> None:
        self.batch_requests: list[dict] = []

    def batch_update(self, body: dict) -> None:
        self.batch_requests.extend(body["requests"])


class FakeWorksheet:
    def __init__(self, values: list[list], sheet_id: int = 111) -> None:
        self.id = sheet_id
        self.spreadsheet = FakeParentSpreadsheet()
        self._values = values
        self.appended: list[list] = []

    def get_all_values(self) -> list[list]:
        return [[_formatted(v) for v in row] for row in self._values]

    def get_values(self, range_name: str, value_render_option: str | None = None) -> list[list]:
        assert value_render_option == "UNFORMATTED_VALUE"
        column_index = HEADER.index("受領日")
        return [[row[column_index]] for row in self._values[4:]]

    def append_rows(self, rows: list[list], value_input_option: str | None = None) -> None:
        self.appended.extend(rows)

    def deleted_row_numbers(self) -> list[int]:
        return [
            r["deleteDimension"]["range"]["startIndex"] + 1
            for r in self.spreadsheet.batch_requests
        ]


def _formatted(value: object) -> str:
    return "" if value == "" else str(value)


class FakeSpreadsheet:
    def __init__(self, archive: FakeWorksheet) -> None:
        self._archive = archive

    def worksheet(self, name: str) -> FakeWorksheet:
        return self._archive


class FakeRepo:
    def __init__(self, purchase: FakeWorksheet, archive: FakeWorksheet) -> None:
        self._purchase = purchase
        self._archive = archive

    def open_worksheet(self, sheet_id: str, sheet_name: str) -> FakeWorksheet:
        return self._purchase

    def open_spreadsheet(self, sheet_id: str) -> FakeSpreadsheet:
        return FakeSpreadsheet(self._archive)


class FakeConfig:
    sheet_id = "SID"
    purchase_sheet_name = "仕入管理"


def _purchase(rows: list[list]) -> FakeWorksheet:
    # ヘッダーは4行目。5行目は FIRST_DATA_ROW=6 の対象外なので空行で埋める。
    return FakeWorksheet([["", "", "", ""]] * 3 + [HEADER, ["", "", "", ""]] + rows)


def _run(rows: list[list], today: date) -> FakeWorksheet:
    purchase = _purchase(rows)
    archive = FakeWorksheet([HEADER])
    archive_out_of_stock(FakeConfig(), FakeRepo(purchase, archive), today=today)
    return purchase


def test_archives_out_of_stock_row_received_before_previous_month_end() -> None:
    purchase = _run(
        [["A6", "在庫なし", "0", RECEIVED_2026_08_14]],
        today=date(2026, 10, 2),
    )

    assert purchase.deleted_row_numbers() == [6]


def test_archives_out_of_stock_row_received_on_the_previous_month_end() -> None:
    purchase = _run(
        [["A6", "在庫なし", "0", RECEIVED_2026_09_30]],
        today=date(2026, 10, 2),
    )

    assert purchase.deleted_row_numbers() == [6]


def test_keeps_out_of_stock_row_received_in_the_current_month() -> None:
    purchase = _run(
        [["A6", "在庫なし", "0", RECEIVED_2026_10_01]],
        today=date(2026, 10, 2),
    )

    assert purchase.deleted_row_numbers() == []


def test_keeps_out_of_stock_row_without_received_date() -> None:
    purchase = _run(
        [["A6", "在庫なし", "0", ""]],
        today=date(2026, 10, 2),
    )

    assert purchase.deleted_row_numbers() == []
