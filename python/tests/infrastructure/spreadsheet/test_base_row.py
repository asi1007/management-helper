import pytest
from infrastructure.spreadsheet.base_row import BaseRow

class TestBaseRow:
    def _make_resolver(self, headers: list[str]):
        index_map = {h.strip(): i for i, h in enumerate(headers) if h.strip()}
        def resolver(name: str) -> int:
            key = name.strip()
            if key not in index_map:
                raise ValueError(f'列 "{key}" が見つかりません')
            return index_map[key]
        return resolver

    def test_get_by_column_name(self):
        resolver = self._make_resolver(["ASIN", "SKU", "購入数"])
        row = BaseRow(values=["B001", "SKU-1", "10"], column_index_resolver=resolver, row_number=5)
        assert row.get("ASIN") == "B001"
        assert row.get("SKU") == "SKU-1"
        assert row.get("購入数") == "10"

    def test_get_trims_string_values(self):
        resolver = self._make_resolver(["name"])
        row = BaseRow(values=["  hello  "], column_index_resolver=resolver, row_number=1)
        assert row.get("name") == "hello"

    def test_getitem_by_index(self):
        resolver = self._make_resolver(["A", "B"])
        row = BaseRow(values=["x", "y"], column_index_resolver=resolver, row_number=1)
        assert row[0] == "x"
        assert row[1] == "y"

    def test_row_number(self):
        resolver = self._make_resolver(["A"])
        row = BaseRow(values=["v"], column_index_resolver=resolver, row_number=42)
        assert row.row_number == 42

    def test_get_unknown_column_raises(self):
        resolver = self._make_resolver(["A"])
        row = BaseRow(values=["v"], column_index_resolver=resolver, row_number=1)
        with pytest.raises(ValueError, match="見つかりません"):
            row.get("unknown")

    def test_get_non_string_returns_as_is(self):
        resolver = self._make_resolver(["num"])
        row = BaseRow(values=[42], column_index_resolver=resolver, row_number=1)
        assert row.get("num") == 42
