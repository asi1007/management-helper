"""SKUとして納品プランに投入できるかの判定テスト"""
from __future__ import annotations

import pytest

from domain.shipment.seller_sku import is_usable_sku


@pytest.mark.parametrize("sku", ["XM-ZLBK-D2DZ", "SKU-20260806JB-01", " 9I-MNUC-U0SH "])
def test_正規SKUは有効(sku):
    assert is_usable_sku(sku) is True


@pytest.mark.parametrize("sku", ["", "   ", None])
def test_空は無効(sku):
    assert is_usable_sku(sku) is False


@pytest.mark.parametrize("sku", ["#N/A", "#REF!", "#VALUE!"])
def test_数式エラー値は無効(sku):
    assert is_usable_sku(sku) is False


@pytest.mark.parametrize("sku", ["SKU-20260508124233", "SKU-1234567890"])
def test_仮SKUは無効(sku):
    assert is_usable_sku(sku) is False


def test_数字が9桁以下なら仮SKUとみなさない():
    assert is_usable_sku("SKU-123456789") is True
