"""依頼対象漏れ検知 + ラベル数 vs 指示書数 検証 のテスト"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import pytest
from src.usecases.batch_print_labels import (
    _detect_missing_rows,
    _verify_label_quantity,
)


def _row(row_number: int, sku: str = "OK", fnsku: str = "X001OK", qty: int = 100) -> SimpleNamespace:
    mapping = {"SKU": sku, "FNSKU": fnsku, "購入数": qty}
    return SimpleNamespace(row_number=row_number, get=lambda k, _m=mapping: _m.get(k))


# === 依頼対象漏れ検知 ===
def test_detect_missing_rows_returns_empty_when_all_processed():
    requested = [_row(10), _row(11), _row(12)]
    processed_rows = [10, 11, 12]
    missing = _detect_missing_rows(requested, processed_rows)
    assert missing == []


def test_detect_missing_rows_returns_unprocessed_row_numbers():
    requested = [_row(10), _row(274, fnsku=""), _row(12)]
    processed_rows = [10, 12]  # 274 が漏れた
    missing = _detect_missing_rows(requested, processed_rows)
    assert missing == [274]


def test_detect_missing_rows_multiple():
    requested = [_row(10), _row(274), _row(347, sku=""), _row(12)]
    processed_rows = [10, 12]
    missing = _detect_missing_rows(requested, processed_rows)
    assert missing == [274, 347]


# === ラベル数 vs 指示書数 検証 ===
def test_verify_label_quantity_passes_within_tolerance():
    """SKU別ceil合計と実PDFページ数が許容範囲なら通る"""
    items = [
        {"sku": "A", "quantity": 100},  # ceil(100/40)=3
        {"sku": "B", "quantity": 200},  # ceil(200/40)=5
    ]
    actual_pages = 8  # 期待 3+5=8 ぴったり
    _verify_label_quantity(items, actual_pages)  # no exception


def test_verify_label_quantity_passes_with_small_excess():
    """端数余り (SKU単位ceilより少ない、または +1-2ページ余分) は許容"""
    items = [{"sku": "A", "quantity": 100}]
    _verify_label_quantity(items, 3)  # ceil(100/40)=3 ぴったり
    _verify_label_quantity(items, 4)  # +1 ページ余分は許容
    _verify_label_quantity(items, 2)  # -1 ページも許容 (内部集約のずれ)


def test_verify_label_quantity_fails_on_large_difference():
    """20%以上のずれはエラー"""
    items = [{"sku": "A", "quantity": 100}]  # 期待3ページ
    with pytest.raises(RuntimeError, match=r"ラベル数.*不一致|乖離"):
        _verify_label_quantity(items, 100)  # 全然違う


def test_verify_label_quantity_fails_when_actual_zero():
    items = [{"sku": "A", "quantity": 100}]
    with pytest.raises(RuntimeError):
        _verify_label_quantity(items, 0)


def test_verify_label_quantity_reports_expected_and_actual():
    items = [{"sku": "A", "quantity": 100}, {"sku": "B", "quantity": 100}]
    with pytest.raises(RuntimeError) as exc:
        _verify_label_quantity(items, 50)
    msg = str(exc.value)
    assert "6" in msg  # expected = 3+3
    assert "50" in msg  # actual
