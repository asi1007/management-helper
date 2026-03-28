import pytest
from domain.inspection.entities.inspection_master_item import InspectionMasterItem
from domain.inspection.value_objects.inspection_master_catalog import InspectionMasterCatalog


class TestInspectionMasterCatalog:
    def _make_catalog(self) -> InspectionMasterCatalog:
        items = {
            "B001": InspectionMasterItem(asin="B001", product_name="商品A", inspection_point="傷チェック", detail_instruction_url="https://example.com/a"),
            "B002": InspectionMasterItem(asin="B002", product_name="商品B", inspection_point="動作確認", detail_instruction_url=""),
        }
        return InspectionMasterCatalog(items_by_asin=items)

    def test_has_existing_asin(self):
        assert self._make_catalog().has("B001") is True

    def test_has_missing_asin(self):
        assert self._make_catalog().has("B999") is False

    def test_get_returns_item(self):
        item = self._make_catalog().get("B001")
        assert item is not None
        assert item.product_name == "商品A"

    def test_get_returns_none_for_missing(self):
        assert self._make_catalog().get("B999") is None

    def test_filter_by_asins(self):
        filtered = self._make_catalog().filter_by_asins(["B001"])
        assert filtered.size() == 1
        assert filtered.has("B001")
        assert not filtered.has("B002")

    def test_size(self):
        assert self._make_catalog().size() == 2

    def test_asins(self):
        assert sorted(self._make_catalog().asins()) == ["B001", "B002"]
