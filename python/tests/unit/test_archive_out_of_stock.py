from __future__ import annotations

from datetime import date

from usecases.archive_out_of_stock import archive_out_of_stock


RECEIVED_LAST_MONTH = 46248  # 2026-08-14


def _formatted(value: object) -> str:
    return "" if value == "" else str(value)


class FakeParentSpreadsheet:
    def __init__(self) -> None:
        self.batch_requests: list[dict] = []

    def batch_update(self, body: dict) -> None:
        self.batch_requests.extend(body["requests"])


class FakeWorksheet:
    def __init__(self, values: list[list], title: str, sheet_id: int = 111) -> None:
        self.title = title
        self.id = sheet_id
        self.spreadsheet = FakeParentSpreadsheet()
        self._values = values
        self.appended: list[list] = []

    def get_all_values(self) -> list[list]:
        return [[_formatted(v) for v in row] for row in self._values]

    def get_values(self, range_name: str, value_render_option: str | None = None) -> list[list]:
        return [[row[3]] for row in self._values[4:]]

    def append_rows(self, rows: list[list], value_input_option: str | None = None) -> None:
        self.appended.extend(rows)

    def deleted_row_numbers(self) -> list[int]:
        return [r["deleteDimension"]["range"]["startIndex"] + 1 for r in self.spreadsheet.batch_requests]


class FakeSpreadsheet:
    def __init__(self, archive: FakeWorksheet) -> None:
        self._archive = archive

    def worksheet(self, name: str) -> FakeWorksheet:
        assert name == "過去仕入れログ"
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


HEADER = ["ASIN", "状態", "在庫数", "受領日"]
R = RECEIVED_LAST_MONTH


def _purchase_values() -> list[list]:
    return [
        ["", "", "", ""],
        ["", "", "", ""],
        ["", "", "", ""],
        HEADER,                        # 行4 = ヘッダー
        ["A5", "在庫なし", "0", R],    # 行5: rowNumber<6 で対象外
        ["A6", "在庫なし", "0", R],    # 行6: 対象
        ["A7", "在庫あり", "5", R],    # 行7: 状態が対象外
        ["A8", "在庫なし", "0", R],    # 行8: 対象
    ]


def test_archives_out_of_stock_rows_from_row6() -> None:
    purchase = FakeWorksheet(_purchase_values(), "仕入管理")
    archive = FakeWorksheet([["ASIN", "状態", "在庫数"]], "過去仕入れログ")
    repo = FakeRepo(purchase, archive)

    archive_out_of_stock(FakeConfig(), repo, today=date(2026, 10, 2))

    assert archive.appended == [
        ["A6", "在庫なし", "0", str(R)],
        ["A8", "在庫なし", "0", str(R)],
    ]
    assert purchase.deleted_row_numbers() == [8, 6]  # 降順で1回のbatch_update


def test_no_out_of_stock_rows_is_noop() -> None:
    values = [["", "", "", ""]] * 3 + [
        HEADER,
        ["A5", "在庫あり", "3", R],
        ["A6", "発送済み", "", ""],
    ]
    purchase = FakeWorksheet(values, "仕入管理")
    archive = FakeWorksheet([HEADER], "過去仕入れログ")
    repo = FakeRepo(purchase, archive)

    archive_out_of_stock(FakeConfig(), repo, today=date(2026, 10, 2))

    assert archive.appended == []
    assert purchase.deleted_row_numbers() == []
