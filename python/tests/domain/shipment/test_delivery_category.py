"""納品分類の同居判定テスト"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "src"))

import pytest

from domain.shipment.delivery_category import (
    FASHION,
    NORMAL,
    DeliveryCategoryUndecidable,
    classify_by_cohabitation,
)


def test_同じ群にノーマル代表がいればノーマル():
    category = classify_by_cohabitation(
        target_sku="NEW-1",
        reference_skus={NORMAL: "REF-N", FASHION: "REF-F"},
        packing_groups=[["NEW-1", "REF-N"], ["REF-F"]],
    )

    assert category == NORMAL


def test_同じ群にファッション代表がいればファッション():
    category = classify_by_cohabitation(
        target_sku="NEW-1",
        reference_skus={NORMAL: "REF-N", FASHION: "REF-F"},
        packing_groups=[["REF-N"], ["REF-F", "NEW-1"]],
    )

    assert category == FASHION


def test_どの代表とも同居しなければ判定不能():
    with pytest.raises(DeliveryCategoryUndecidable, match="新しい納品分類"):
        classify_by_cohabitation(
            target_sku="NEW-1",
            reference_skus={NORMAL: "REF-N", FASHION: "REF-F"},
            packing_groups=[["REF-N"], ["REF-F"], ["NEW-1"]],
        )


def test_代表どうしが同居していれば判定不能():
    with pytest.raises(DeliveryCategoryUndecidable, match="代表"):
        classify_by_cohabitation(
            target_sku="NEW-1",
            reference_skus={NORMAL: "REF-N", FASHION: "REF-F"},
            packing_groups=[["NEW-1", "REF-N", "REF-F"]],
        )


def test_対象SKUが群に含まれなければ判定不能():
    with pytest.raises(DeliveryCategoryUndecidable, match="対象SKU"):
        classify_by_cohabitation(
            target_sku="NEW-1",
            reference_skus={NORMAL: "REF-N", FASHION: "REF-F"},
            packing_groups=[["REF-N"], ["REF-F"]],
        )


def test_代表がひとつも群に含まれなければ判定不能():
    with pytest.raises(DeliveryCategoryUndecidable, match="代表"):
        classify_by_cohabitation(
            target_sku="NEW-1",
            reference_skus={NORMAL: "REF-N", FASHION: "REF-F"},
            packing_groups=[["NEW-1"]],
        )


def test_SKUの前後空白は無視される():
    category = classify_by_cohabitation(
        target_sku=" NEW-1 ",
        reference_skus={NORMAL: "REF-N ", FASHION: " REF-F"},
        packing_groups=[["NEW-1", " REF-N"], ["REF-F"]],
    )

    assert category == NORMAL
