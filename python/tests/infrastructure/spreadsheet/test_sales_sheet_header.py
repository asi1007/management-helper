from __future__ import annotations

import pytest

from infrastructure.spreadsheet.sales_sheet import SalesSheet


HEADER = ["ASIN", "発注数", "SKU", "fnsku"]


class TestFindHeaderRow:
    def test_4行目にあれば3を返す(self) -> None:
        values = [["x"], ["y"], ["z"], HEADER, ["B0TEST", "1", "SKU-A", "X001"]]
        assert SalesSheet._find_header_row(values, ["ASIN", "SKU", "fnsku"]) == 3

    def test_行が1つ増えて5行目になっても追従する(self) -> None:
        values = [["x"], ["y"], ["z"], ["利益率"], HEADER, ["B0TEST", "1", "SKU-A", "X001"]]
        assert SalesSheet._find_header_row(values, ["ASIN", "SKU", "fnsku"]) == 4

    def test_必要な列が揃った最初の行を選ぶ(self) -> None:
        # ASIN だけある行を先に置いても、3列揃う行まで進む
        values = [["ASIN", "発注量"], HEADER]
        assert SalesSheet._find_header_row(values, ["ASIN", "SKU", "fnsku"]) == 1

    def test_前後に空白があっても一致させる(self) -> None:
        values = [[" ASIN ", "SKU", " fnsku"]]
        assert SalesSheet._find_header_row(values, ["ASIN", "SKU", "fnsku"]) == 0

    def test_見つからなければエラー(self) -> None:
        with pytest.raises(ValueError, match="ヘッダー"):
            SalesSheet._find_header_row([["a"], ["b"]], ["ASIN", "SKU", "fnsku"])

    def test_探索範囲を超えた行は見ない(self) -> None:
        values = [["x"]] * 40 + [HEADER]
        with pytest.raises(ValueError):
            SalesSheet._find_header_row(values, ["ASIN", "SKU", "fnsku"])
