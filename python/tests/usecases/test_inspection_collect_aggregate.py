from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from src.usecases.create_inspection_sheet import _collect_matched_items


def _row(asin: str, sku: str, qty: int, order: str = "") -> SimpleNamespace:
    mapping = {"ASIN": asin, "SKU": sku, "購入数": qty, "注文番号": order}
    return SimpleNamespace(get=lambda k, _m=mapping: _m.get(k))


def _catalog(items: dict):
    return SimpleNamespace(get=lambda asin, _items=items: _items.get(asin))


def _master(name: str, detail_url: str = "https://example.com/sheet") -> SimpleNamespace:
    return SimpleNamespace(product_name=name, inspection_point="POINT", detail_instruction_url=detail_url)


def test_aggregates_same_sku_rows():
    rows = [
        _row("ASIN-A", "SKU-A", 600, "P1"),
        _row("ASIN-A", "SKU-A", 600, "P2"),
        _row("ASIN-A", "SKU-A", 600, "P3"),
        _row("ASIN-B", "SKU-B", 100, "P10"),
    ]
    catalog = _catalog({"ASIN-A": _master("A6 フォトフレーム"), "ASIN-B": _master("B5 フォトフレーム")})

    matched = _collect_matched_items(rows, catalog)

    assert len(matched) == 2
    assert matched[0]["asin"] == "ASIN-A"
    assert matched[0]["quantity"] == 1800
    assert "P1" in matched[0]["order_no"]
    assert "P2" in matched[0]["order_no"]
    assert "P3" in matched[0]["order_no"]
    assert matched[1]["asin"] == "ASIN-B"
    assert matched[1]["quantity"] == 100


def test_preserves_first_seen_order():
    rows = [
        _row("ASIN-B", "SKU-B", 100),
        _row("ASIN-A", "SKU-A", 300),
        _row("ASIN-B", "SKU-B", 200),
    ]
    catalog = _catalog({"ASIN-A": _master("A"), "ASIN-B": _master("B")})

    matched = _collect_matched_items(rows, catalog)

    assert len(matched) == 2
    assert matched[0]["asin"] == "ASIN-B"
    assert matched[0]["quantity"] == 300
    assert matched[1]["asin"] == "ASIN-A"


def test_different_sku_same_asin_kept_separate():
    rows = [
        _row("ASIN-A", "SKU-A1", 100),
        _row("ASIN-A", "SKU-A2", 200),  # 別 SKU は集約しない
    ]
    catalog = _catalog({"ASIN-A": _master("A")})

    matched = _collect_matched_items(rows, catalog)

    assert len(matched) == 2
    assert matched[0]["quantity"] == 100
    assert matched[1]["quantity"] == 200


def test_skips_rows_without_master_entry():
    rows = [
        _row("ASIN-X", "SKU-X", 100),
        _row("ASIN-A", "SKU-A", 200),
    ]
    catalog = _catalog({"ASIN-A": _master("A")})  # X は master 未登録

    matched = _collect_matched_items(rows, catalog)

    assert len(matched) == 1
    assert matched[0]["asin"] == "ASIN-A"
    assert matched[0]["quantity"] == 200


def test_deduplicates_identical_order_numbers():
    rows = [
        _row("ASIN-A", "SKU-A", 100, "P1"),
        _row("ASIN-A", "SKU-A", 200, "P1"),  # 同じ注文番号
    ]
    catalog = _catalog({"ASIN-A": _master("A")})

    matched = _collect_matched_items(rows, catalog)
    assert len(matched) == 1
    assert matched[0]["quantity"] == 300
    assert matched[0]["order_no"] == "P1"


def test_falls_back_to_asin_when_sku_empty():
    rows = [
        _row("ASIN-A", "", 100, "P1"),
        _row("ASIN-A", "", 200, "P2"),
    ]
    catalog = _catalog({"ASIN-A": _master("A")})

    matched = _collect_matched_items(rows, catalog)
    assert len(matched) == 1
    assert matched[0]["quantity"] == 300
