from __future__ import annotations

from infrastructure.spreadsheet.sales_sheet import SalesSheet


class _FakeWorksheet:
    def __init__(self, values: list[list[str]]) -> None:
        self._values = values
        self.updated: list[tuple[int, int, str]] = []

    def get_all_values(self) -> list[list[str]]:
        return self._values

    def update_cell(self, row: int, col: int, value: str) -> None:
        self.updated.append((row, col, value))


def _sheet(values: list[list[str]]) -> SalesSheet:
    s = SalesSheet.__new__(SalesSheet)
    s._worksheet = _FakeWorksheet(values)
    s._repo = None
    return s


HEADER = ["ASIN", "SKU", "fnsku", "納品分類"]


class TestWriteDeliveryCategory:
    def test_ヘッダーが4行目のとき正しい行に書く(self) -> None:
        values = [["x"], ["y"], ["z"], HEADER, ["B0AAA", "S", "F", ""], ["B0BBB", "S", "F", ""]]
        sheet = _sheet(values)
        written = sheet.write_delivery_category("B0BBB", "ノーマル")
        assert written == [6]
        assert sheet._worksheet.updated == [(6, 4, "ノーマル")]

    def test_ヘッダーが5行目へずれても追従する(self) -> None:
        values = [["x"], ["y"], ["z"], ["利益率"], HEADER, ["B0AAA", "S", "F", ""], ["B0BBB", "S", "F", ""]]
        sheet = _sheet(values)
        written = sheet.write_delivery_category("B0BBB", "ノーマル")
        assert written == [7]
        assert sheet._worksheet.updated == [(7, 4, "ノーマル")]

    def test_同じASINが複数行あればすべて書く(self) -> None:
        values = [HEADER, ["B0AAA", "S", "F", ""], ["B0BBB", "S", "F", ""], ["B0AAA", "S", "F", ""]]
        sheet = _sheet(values)
        assert sheet.write_delivery_category("B0AAA", "ノーマル") == [2, 4]
