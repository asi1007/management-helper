from pathlib import Path
from infrastructure.amazon.downloader import Downloader

class TestSplitByQuantityLimit:
    def test_no_split_when_under_15000(self):
        dl = Downloader(auth_token="dummy", save_dir=Path("/tmp"))
        items = [{"msku": "A", "quantity": 100}]
        chunks = dl._split_by_quantity_limit(items)
        assert len(chunks) == 1
        assert chunks[0] == items

    def test_no_split_single_item_over_999_but_under_15000(self):
        dl = Downloader(auth_token="dummy", save_dir=Path("/tmp"))
        items = [{"msku": "A", "quantity": 3000}]
        chunks = dl._split_by_quantity_limit(items)
        assert len(chunks) == 1

    def test_splits_when_over_15000(self):
        dl = Downloader(auth_token="dummy", save_dir=Path("/tmp"))
        items = [{"msku": "A", "quantity": 16000}]
        chunks = dl._split_by_quantity_limit(items)
        assert len(chunks) > 1
        total = sum(item["quantity"] for chunk in chunks for item in chunk)
        assert total == 16000

    def test_each_chunk_under_999_when_split(self):
        dl = Downloader(auth_token="dummy", save_dir=Path("/tmp"))
        items = [{"msku": "A", "quantity": 16000}]
        chunks = dl._split_by_quantity_limit(items)
        for chunk in chunks:
            chunk_total = sum(item["quantity"] for item in chunk)
            assert chunk_total <= 999
