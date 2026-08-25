from unittest.mock import MagicMock

import pytest

from infrastructure.spreadsheet.home_shipment_sheet import HomeShipmentSheet

HOME_SHIPMENT_HEADER = [
    "梱包依頼日", "自宅到着日", "追跡番号", "DATE_ORDER", "行番号",
    "ASIN_SELL", "IMAGE", "TITLE_SELL", "INBOUND_PLAN", "", "QTY", "MyUS",
]
HOME_SHIPMENT_ROW = [
    "07/07", "", "", "05-13", "84",
    "B0F5P3RM78", "", "商品名", "", "", "304", "Y0806-260513006",
]


class TestHomeShipmentSheetColumnAliases:
    def _make_sheet(self, header: list[str], row: list[str]) -> HomeShipmentSheet:
        mock_worksheet = MagicMock()
        mock_worksheet.get_all_values.return_value = [["注意書き"], ["注意書き"], header, row]
        mock_repo = MagicMock()
        mock_repo.open_worksheet.return_value = mock_worksheet
        return HomeShipmentSheet(mock_repo, "test-id", "自宅発送")

    def test_asin_resolves_to_asin_sell(self):
        sheet = self._make_sheet(HOME_SHIPMENT_HEADER, HOME_SHIPMENT_ROW)
        assert sheet.data[0].get("ASIN") == "B0F5P3RM78"

    def test_purchase_date_resolves_to_date_order(self):
        sheet = self._make_sheet(HOME_SHIPMENT_HEADER, HOME_SHIPMENT_ROW)
        assert sheet.data[0].get("購入日") == "05-13"

    def test_order_number_resolves_to_myus(self):
        sheet = self._make_sheet(HOME_SHIPMENT_HEADER, HOME_SHIPMENT_ROW)
        assert sheet.data[0].get("注文番号") == "Y0806-260513006"

    def test_japanese_header_still_wins(self):
        header = ["行番号", "ASIN", "購入日", "注文番号", "ASIN_SELL"]
        row = ["84", "B000000001", "2026/05/13", "Y-1", "B999999999"]
        sheet = self._make_sheet(header, row)
        assert sheet.data[0].get("ASIN") == "B000000001"
        assert sheet.data[0].get("購入日") == "2026/05/13"
        assert sheet.data[0].get("注文番号") == "Y-1"

    def test_unknown_column_raises_with_original_name(self):
        sheet = self._make_sheet(HOME_SHIPMENT_HEADER, HOME_SHIPMENT_ROW)
        with pytest.raises(ValueError, match='列 "存在しない列" が見つかりません'):
            sheet.data[0].get("存在しない列")

    def test_alias_missing_from_header_raises_with_original_name(self):
        header = ["行番号", "追跡番号"]
        row = ["84", "1234"]
        sheet = self._make_sheet(header, row)
        with pytest.raises(ValueError, match='列 "ASIN" が見つかりません'):
            sheet.data[0].get("ASIN")
