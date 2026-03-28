import pytest
from domain.label.services.label_aggregator import LabelAggregator


class FakeRow:
    def __init__(self, data: dict[str, str]):
        self._data = data

    def get(self, column_name: str) -> str:
        return self._data.get(column_name, "")


class TestLabelAggregator:
    def test_aggregate_single_sku(self):
        rows = [FakeRow({"SKU": "SKU-1", "購入数": "10"})]
        items = LabelAggregator().aggregate(rows)
        assert len(items) == 1
        assert items[0].sku == "SKU-1"
        assert items[0].quantity == 10

    def test_aggregate_merges_same_sku(self):
        rows = [FakeRow({"SKU": "SKU-1", "購入数": "10"}), FakeRow({"SKU": "SKU-1", "購入数": "5"})]
        items = LabelAggregator().aggregate(rows)
        assert len(items) == 1
        assert items[0].quantity == 15

    def test_aggregate_multiple_skus(self):
        rows = [FakeRow({"SKU": "SKU-1", "購入数": "10"}), FakeRow({"SKU": "SKU-2", "購入数": "20"})]
        items = LabelAggregator().aggregate(rows)
        assert len(items) == 2

    def test_aggregate_skips_empty_sku(self):
        rows = [FakeRow({"SKU": "", "購入数": "10"}), FakeRow({"SKU": "SKU-1", "購入数": "5"})]
        items = LabelAggregator().aggregate(rows)
        assert len(items) == 1

    def test_aggregate_no_valid_skus_raises(self):
        rows = [FakeRow({"SKU": "", "購入数": "0"})]
        with pytest.raises(ValueError, match="有効なSKUがありません"):
            LabelAggregator().aggregate(rows)

    def test_aggregate_empty_rows_raises(self):
        with pytest.raises(ValueError, match="有効なSKUがありません"):
            LabelAggregator().aggregate([])
