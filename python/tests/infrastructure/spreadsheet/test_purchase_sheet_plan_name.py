from __future__ import annotations

from typing import Any

import pytest

from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet


class _Row:
    def __init__(self, category: str, row_number: int = 10) -> None:
        self.row_number = row_number
        self._d = {"納品分類": category}

    def get(self, key: str) -> Any:
        return self._d.get(key, "")


@pytest.fixture
def sheet() -> PurchaseSheet:
    s = PurchaseSheet.__new__(PurchaseSheet)
    s.data = [_Row("ノーマル")]
    s._format_date_mmdd = lambda: "09/10"  # type: ignore[method-assign]
    return s


class TestPlanNameSuffix:
    def test_既定では分類名のまま(self, sheet) -> None:
        assert sheet._generate_plan_name_text() == "09/10ノーマル"

    def test_空輸なら末尾に空輸を付ける(self, sheet) -> None:
        assert sheet._generate_plan_name_text(suffix="空輸") == "09/10ノーマル空輸"

    def test_空文字のsuffixは付けない(self, sheet) -> None:
        assert sheet._generate_plan_name_text(suffix="") == "09/10ノーマル"

    def test_前後の空白は落とす(self, sheet) -> None:
        assert sheet._generate_plan_name_text(suffix="  空輸  ") == "09/10ノーマル空輸"

    def test_対象行が無くても日付は出す(self, sheet) -> None:
        sheet.data = []
        assert sheet._generate_plan_name_text(suffix="空輸") == "09/10空輸"


class TestWritePlanNameToRows:
    def test_行ごとの分類にsuffixを付けて書く(self, sheet) -> None:
        written: list[Any] = []

        def fake_write(column_name: str, value_func: Any) -> int:
            for i, row in enumerate(sheet.data):
                written.append(value_func(row, i))
            return len(written)

        sheet.write_column_by_func = fake_write  # type: ignore[method-assign]
        sheet.data = [_Row("ノーマル"), _Row("ファッション", 11)]
        sheet.write_plan_name_to_rows(None, suffix="空輸")
        assert written == ["09/10ノーマル空輸", "09/10ファッション空輸"]

    def test_指示書URLがあればHYPERLINKの表示名にsuffixが入る(self, sheet) -> None:
        written: list[Any] = []

        def fake_write(column_name: str, value_func: Any) -> int:
            for i, row in enumerate(sheet.data):
                written.append(value_func(row, i))
            return len(written)

        sheet.write_column_by_func = fake_write  # type: ignore[method-assign]
        sheet.write_plan_name_to_rows("/path/0910ノーマル指示書.xlsx", suffix="空輸")
        assert written[0]["type"] == "formula"
        assert '"09/10ノーマル空輸"' in written[0]["value"]

    def test_suffix無しなら従来どおり(self, sheet) -> None:
        written: list[Any] = []

        def fake_write(column_name: str, value_func: Any) -> int:
            for i, row in enumerate(sheet.data):
                written.append(value_func(row, i))
            return len(written)

        sheet.write_column_by_func = fake_write  # type: ignore[method-assign]
        sheet.write_plan_name_to_rows(None)
        assert written == ["09/10ノーマル"]
