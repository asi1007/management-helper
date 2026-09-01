from pathlib import Path

from infrastructure.amazon.downloader import (
    MAX_ITEMS_PER_REQUEST,
    MAX_QUANTITY_PER_MSKU,
    Downloader,
)


def _downloader() -> Downloader:
    return Downloader(auth_token="dummy", save_dir=Path("/tmp"))


class TestSplitByQuantityLimit:
    def test_keeps_single_chunk_when_within_api_limits(self):
        items = [{"msku": "A", "quantity": 100}, {"msku": "B", "quantity": 5000}]

        assert _downloader()._split_by_quantity_limit(items) == [items]

    def test_splits_msku_exceeding_quantity_maximum(self):
        chunks = _downloader()._split_by_quantity_limit([{"msku": "A", "quantity": 16000}])

        entries = [entry for chunk in chunks for entry in chunk]
        assert [e["quantity"] for e in entries] == [MAX_QUANTITY_PER_MSKU, 6000]
        assert all(e["msku"] == "A" for e in entries)

    def test_every_entry_within_quantity_maximum(self):
        chunks = _downloader()._split_by_quantity_limit([{"msku": "A", "quantity": 25000}])

        assert all(e["quantity"] <= MAX_QUANTITY_PER_MSKU for chunk in chunks for e in chunk)

    def test_preserves_total_quantity_when_split(self):
        chunks = _downloader()._split_by_quantity_limit([{"msku": "A", "quantity": 16000}])

        assert sum(e["quantity"] for chunk in chunks for e in chunk) == 16000

    def test_caps_each_chunk_at_item_maximum(self):
        items = [{"msku": f"SKU{i}", "quantity": 1} for i in range(MAX_ITEMS_PER_REQUEST + 50)]

        chunks = _downloader()._split_by_quantity_limit(items)

        assert [len(chunk) for chunk in chunks] == [MAX_ITEMS_PER_REQUEST, 50]

    def test_keeps_all_mskus_when_chunked_by_item_count(self):
        items = [{"msku": f"SKU{i}", "quantity": 1} for i in range(MAX_ITEMS_PER_REQUEST + 50)]

        chunks = _downloader()._split_by_quantity_limit(items)

        assert [e for chunk in chunks for e in chunk] == items
