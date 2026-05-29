"""PurchaseSheet.write_trial_plan_url のテスト"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet


def test_write_trial_plan_url_writes_hyperlink_to_each_row(mocker):
    """指定された rows の「納品プラン」列に HYPERLINK 数式を書き込む"""
    sheet = mocker.Mock(spec=PurchaseSheet)
    sheet.write_trial_plan_url = PurchaseSheet.write_trial_plan_url.__get__(sheet)
    sheet._get_column_index_by_name = mocker.Mock(return_value=20)  # 21列目 (1-indexed)
    sheet.write_formula = mocker.Mock()

    rows = [
        SimpleNamespace(row_number=340),
        SimpleNamespace(row_number=341),
    ]
    url = "https://sellercentral.amazon.co.jp/fba/sendtoamazon/confirm_content_step?wf=wf999"
    plan_id = "wf999XYZ"

    sheet.write_trial_plan_url(rows, url, plan_id)

    assert sheet.write_formula.call_count == 2
    args_1 = sheet.write_formula.call_args_list[0].args
    assert args_1[0] == 340
    assert args_1[1] == 21  # plan_col = index + 1
    assert "wf999" in args_1[2]
    assert "HYPERLINK" in args_1[2]
