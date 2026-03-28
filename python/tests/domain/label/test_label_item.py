import pytest
from domain.label.entities.label_item import LabelItem


class TestLabelItem:
    def test_valid_creation(self):
        item = LabelItem(sku="TEST-SKU", quantity=10)
        assert item.sku == "TEST-SKU"
        assert item.quantity == 10

    def test_trims_sku(self):
        item = LabelItem(sku="  TEST-SKU  ", quantity=5)
        assert item.sku == "TEST-SKU"

    def test_empty_sku_raises(self):
        with pytest.raises(ValueError, match="SKUが空です"):
            LabelItem(sku="", quantity=10)

    def test_zero_quantity_raises(self):
        with pytest.raises(ValueError, match="数量が不正です"):
            LabelItem(sku="SKU", quantity=0)

    def test_negative_quantity_raises(self):
        with pytest.raises(ValueError, match="数量が不正です"):
            LabelItem(sku="SKU", quantity=-1)

    def test_to_msku_quantity(self):
        item = LabelItem(sku="SKU-001", quantity=5)
        assert item.to_msku_quantity() == {"msku": "SKU-001", "quantity": 5}
