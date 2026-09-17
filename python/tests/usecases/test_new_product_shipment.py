from __future__ import annotations

import pytest

from usecases.new_product_shipment import (
    FIRST_PURCHASE_COUNT,
    NewProductRow,
    select_new_product_rows,
    summarize_by_category,
)


class _Row:
    def __init__(self, row_number: int, **kw) -> None:
        self.row_number = row_number
        self._d = {
            "ASIN": "B0TEST00001", "商品名": "商品", "購入数": "700",
            "仕入回数": "1", "納品分類": "ノーマル", "SKU": "S-1", "FNSKU": "X001",
            "購入日": "09-11", "到着日": "09/16",
        }
        self._d.update({k: str(v) for k, v in kw.items()})

    def get(self, key, default=None):
        return self._d.get(key, default)


class TestSelectNewProductRows:
    def test_仕入回数1だけを選ぶ(self) -> None:
        rows = [_Row(1, 仕入回数="1"), _Row(2, 仕入回数="2"), _Row(3, 仕入回数="1")]
        assert [r.row_number for r in select_new_product_rows(rows)] == [1, 3]

    def test_初回の定義は1(self) -> None:
        assert FIRST_PURCHASE_COUNT == 1

    def test_空白や前後の空白を許容する(self) -> None:
        assert [r.row_number for r in select_new_product_rows([_Row(1, 仕入回数=" 1 ")])] == [1]

    def test_仕入回数が空の行は選ばない(self) -> None:
        assert select_new_product_rows([_Row(1, 仕入回数="")]) == []

    def test_数値でない仕入回数は選ばない(self) -> None:
        assert select_new_product_rows([_Row(1, 仕入回数="初回")]) == []

    def test_ASINが無い行は選ばない(self) -> None:
        assert select_new_product_rows([_Row(1, ASIN="")]) == []

    def test_行番号の昇順で返す(self) -> None:
        rows = [_Row(9), _Row(3), _Row(5)]
        assert [r.row_number for r in select_new_product_rows(rows)] == [3, 5, 9]


class TestSummarizeByCategory:
    def test_納品分類ごとに件数と数量をまとめる(self) -> None:
        rows = [
            _Row(1, 納品分類="ノーマル", 購入数="700"),
            _Row(2, 納品分類="ノーマル", 購入数="300"),
            _Row(3, 納品分類="ファッション", 購入数="500"),
        ]
        got = summarize_by_category(select_new_product_rows(rows))
        assert got["ノーマル"].row_count == 2
        assert got["ノーマル"].total_quantity == 1000
        assert got["ファッション"].total_quantity == 500

    def test_納品分類が空なら未分類にまとめる(self) -> None:
        got = summarize_by_category(select_new_product_rows([_Row(1, 納品分類="")]))
        assert "未分類" in got

    def test_SKUかFNSKUが欠けている行を数える(self) -> None:
        rows = [_Row(1, SKU=""), _Row(2, FNSKU=""), _Row(3)]
        got = summarize_by_category(select_new_product_rows(rows))
        assert got["ノーマル"].missing_identifier_rows == [1, 2]

    def test_購入数が数値でなくても落ちない(self) -> None:
        got = summarize_by_category(select_new_product_rows([_Row(1, 購入数="")]))
        assert got["ノーマル"].total_quantity == 0


class TestNewProductRow:
    def test_行から必要な情報を取り出す(self) -> None:
        entry = NewProductRow.from_row(_Row(255, 商品名="キーリングハンガー", 購入数="700"))
        assert entry.row_number == 255
        assert entry.product_name == "キーリングハンガー"
        assert entry.quantity == 700
        assert entry.category == "ノーマル"

    def test_識別子が揃っているかを持つ(self) -> None:
        assert NewProductRow.from_row(_Row(1)).has_identifiers is True
        assert NewProductRow.from_row(_Row(1, FNSKU="")).has_identifiers is False
