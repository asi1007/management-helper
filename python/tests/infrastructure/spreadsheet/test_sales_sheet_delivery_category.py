"""売上/日シートの納品分類の読み書きテスト"""
from __future__ import annotations

import pytest

from infrastructure.spreadsheet.sales_sheet import SalesSheet

HEADER = ["ASIN", "SKU", "fnsku", "納品分類"]


def _sheet(mocker, rows: list[list[str]]) -> tuple[SalesSheet, object]:
    worksheet = mocker.Mock()
    worksheet.get_all_values.return_value = [[], [], [], HEADER, *rows]
    repo = mocker.Mock()
    repo.open_worksheet.return_value = worksheet
    return SalesSheet(repo), worksheet


def test_ASINから納品分類を引ける(mocker):
    sheet, _ = _sheet(mocker, [
        ["B001", "SKU-1", "X001", "ノーマル"],
        ["B002", "SKU-2", "X002", "ファッション"],
    ])

    assert sheet.load_delivery_category_by_asin() == {"B001": "ノーマル", "B002": "ファッション"}


def test_納品分類が空の行は返らない(mocker):
    sheet, _ = _sheet(mocker, [["B001", "SKU-1", "X001", "  "]])

    assert sheet.load_delivery_category_by_asin() == {}


def test_納品分類を該当行すべてに書き込む(mocker):
    sheet, worksheet = _sheet(mocker, [
        ["B001", "SKU-1", "X001", ""],
        ["B002", "SKU-2", "X002", "ノーマル"],
        ["B001", "SKU-1", "X001", ""],
    ])

    written = sheet.write_delivery_category("B001", "ファッション")

    assert written == [5, 7]
    assert worksheet.update_cell.call_count == 2
    assert worksheet.update_cell.call_args_list[0].args == (5, 4, "ファッション")
    assert worksheet.update_cell.call_args_list[1].args == (7, 4, "ファッション")


def test_該当ASINが無ければ書き込まない(mocker):
    sheet, worksheet = _sheet(mocker, [["B001", "SKU-1", "X001", ""]])

    with pytest.raises(ValueError, match="B999"):
        sheet.write_delivery_category("B999", "ノーマル")
    worksheet.update_cell.assert_not_called()


def test_既存のASIN_SKU_fnsku取得は従来どおり動く(mocker):
    sheet, _ = _sheet(mocker, [["B001", "SKU-1", "X001", "ノーマル"]])

    assert sheet.load_asin_to_sku_fnsku() == {"B001": {"sku": "SKU-1", "fnsku": "X001"}}
