from unittest.mock import MagicMock
import pytest
from infrastructure.spreadsheet.base_sheet import BaseSheet

class TestBaseSheet:
    def _make_sheet(self, all_values: list[list[str]], header_row: int = 1) -> BaseSheet:
        mock_worksheet = MagicMock()
        mock_worksheet.get_all_values.return_value = all_values
        mock_repo = MagicMock()
        mock_repo.open_worksheet.return_value = mock_worksheet
        return BaseSheet(repo=mock_repo, sheet_id="test-id", sheet_name="test-sheet", header_row=header_row)

    def test_loads_data_rows(self):
        all_values = [["ASIN", "SKU", "購入数"], ["B001", "SKU-1", "10"], ["B002", "SKU-2", "20"]]
        sheet = self._make_sheet(all_values)
        assert len(sheet.data) == 2
        assert sheet.data[0].get("ASIN") == "B001"
        assert sheet.data[1].get("購入数") == "20"

    def test_row_numbers_start_after_header(self):
        all_values = [["A"], ["v1"], ["v2"]]
        sheet = self._make_sheet(all_values)
        assert sheet.data[0].row_number == 2
        assert sheet.data[1].row_number == 3

    def test_header_row_4(self):
        all_values = [["x"], ["x"], ["x"], ["ASIN", "SKU"], ["B001", "SKU-1"]]
        sheet = self._make_sheet(all_values, header_row=4)
        assert len(sheet.data) == 1
        assert sheet.data[0].get("ASIN") == "B001"
        assert sheet.data[0].row_number == 5

    def test_get_rows_by_numbers(self):
        all_values = [["A"], ["v1"], ["v2"], ["v3"]]
        sheet = self._make_sheet(all_values)
        rows = sheet.get_rows_by_numbers([2, 4])
        assert len(rows) == 2
        assert rows[0].row_number == 2
        assert rows[1].row_number == 4

    def test_filter(self):
        all_values = [["status", "name"], ["active", "a"], ["inactive", "b"], ["active", "c"]]
        sheet = self._make_sheet(all_values)
        rows = sheet.filter("status", ["active"])
        assert len(rows) == 2
        assert rows[0].get("name") == "a"
        assert rows[1].get("name") == "c"

    def test_unknown_column_raises(self):
        all_values = [["A"], ["v"]]
        sheet = self._make_sheet(all_values)
        with pytest.raises(ValueError, match="見つかりません"):
            sheet.filter("unknown", ["x"])
