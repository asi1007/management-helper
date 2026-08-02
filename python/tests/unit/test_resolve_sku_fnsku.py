from __future__ import annotations

from usecases.fill_sku_fnsku_from_shipment import _resolve_sku_fnsku


# pairs: list[tuple[sku, fnsku]]
def test_fill_fnsku_when_sku_present():
    pairs = [("DB-T0OT-ZDCG", "X001APUHB1"), ("DL-H48F-39WT", "X002")]
    sku, fnsku = _resolve_sku_fnsku("DB-T0OT-ZDCG", "", pairs, asin="", asin_map={})
    assert sku is None and fnsku == "X001APUHB1"


def test_fill_sku_when_fnsku_present():
    pairs = [("DB-T0OT-ZDCG", "X001APUHB1")]
    sku, fnsku = _resolve_sku_fnsku("", "X001APUHB1", pairs, asin="", asin_map={})
    assert sku == "DB-T0OT-ZDCG" and fnsku is None


def test_both_empty_single_pair_fills_both():
    pairs = [("DB-T0OT-ZDCG", "X001APUHB1")]
    sku, fnsku = _resolve_sku_fnsku("", "", pairs, asin="B0FCHM6QQR", asin_map={})
    assert sku == "DB-T0OT-ZDCG" and fnsku == "X001APUHB1"


def test_both_empty_multi_pair_uses_asin_map():
    pairs = [("DB-T0OT-ZDCG", "X001APUHB1"), ("DL-H48F-39WT", "X002")]
    asin_map = {"B0FCHM6QQR": ("DB-T0OT-ZDCG", "X001APUHB1")}
    sku, fnsku = _resolve_sku_fnsku("", "", pairs, asin="B0FCHM6QQR", asin_map=asin_map)
    assert sku == "DB-T0OT-ZDCG" and fnsku == "X001APUHB1"


def test_both_empty_multi_pair_ambiguous_returns_none():
    pairs = [("DB-T0OT-ZDCG", "X001APUHB1"), ("DL-H48F-39WT", "X002")]
    sku, fnsku = _resolve_sku_fnsku("", "", pairs, asin="B0UNKNOWN", asin_map={})
    assert sku is None and fnsku is None


def test_no_matching_pair_returns_none():
    pairs = [("OTHER", "XZZZ")]
    sku, fnsku = _resolve_sku_fnsku("DB-T0OT-ZDCG", "", pairs, asin="", asin_map={})
    assert sku is None and fnsku is None
