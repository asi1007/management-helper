from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import pytest
from src.usecases.batch_print_labels import _validate_sku_fnsku


def _row(row_number: int, sku: str = "", fnsku: str = "") -> SimpleNamespace:
    mapping = {"SKU": sku, "FNSKU": fnsku}
    obj = SimpleNamespace(row_number=row_number, get=lambda k, _m=mapping: _m.get(k))
    return obj


def test_passes_when_all_skus_and_fnskus_present():
    rows = [
        _row(10, sku="ABC-DEF-GHI", fnsku="X001ABC"),
        _row(11, sku="JKL-MNO-PQR", fnsku="X001DEF"),
    ]
    _validate_sku_fnsku(rows)  # no exception


def test_raises_on_blank_sku():
    rows = [_row(10, sku="", fnsku="X001ABC")]
    with pytest.raises(RuntimeError, match=r"SKU.*行.*10"):
        _validate_sku_fnsku(rows)


def test_raises_on_blank_fnsku():
    rows = [_row(10, sku="ABC-DEF-GHI", fnsku="")]
    with pytest.raises(RuntimeError, match=r"FNSKU.*行.*10"):
        _validate_sku_fnsku(rows)


def test_passes_with_provisional_sku_when_fnsku_present():
    """仮SKU でも FNSKU があれば SP-API は通るので、エラーにしない (2026-05-18 緩和)"""
    rows = [_row(274, sku="SKU-20260508124233", fnsku="X001DF59FR")]
    _validate_sku_fnsku(rows)  # no exception


def test_reports_multiple_offending_rows():
    rows = [
        _row(10, sku="", fnsku="X001ABC"),
        _row(11, sku="ABC", fnsku=""),
        _row(13, sku="OK-SKU", fnsku="X001GOOD"),
    ]
    with pytest.raises(RuntimeError) as exc:
        _validate_sku_fnsku(rows)
    msg = str(exc.value)
    assert "10" in msg
    assert "11" in msg
