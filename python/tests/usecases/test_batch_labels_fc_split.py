"""FC分割pre-checkのテスト"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import pytest
from src.usecases.batch_print_labels import _check_fc_split_for_all_groups


def _row(row_number: int, sku: str, asin: str = "B000ASIN", qty: int = 100) -> SimpleNamespace:
    mapping = {"SKU": sku, "ASIN": asin, "FNSKU": f"X001{sku}", "購入数": qty, "納品分類": "ノーマル"}
    return SimpleNamespace(row_number=row_number, get=lambda k, _m=mapping: _m.get(k))


def _make_creator_mock(mocker, plan_id: str, packing_groups: list[dict]) -> object:
    creator = mocker.Mock()
    creator.create_plan.return_value = {
        "inboundPlanId": plan_id,
        "link": f"https://sellercentral.amazon.co.jp/fba/sendtoamazon/confirm_content_step?wf={plan_id}",
    }
    creator.get_packing_groups.return_value = packing_groups
    return creator


def test_check_fc_split_single_group_passes(mocker):
    """1 packingGroup なら例外なし、シートに納品プラン URL を書き込む"""
    rows = [_row(340, "SKU_A"), _row(341, "SKU_B")]
    groups = {"ノーマル": rows}
    sheet = mocker.Mock()
    creator = _make_creator_mock(mocker, "wf111", [{"packingGroupId": "pg-a"}])

    _check_fc_split_for_all_groups(groups, creator, sheet)

    creator.create_plan.assert_called_once()
    creator.get_packing_groups.assert_called_once_with("wf111")
    # 「納品プラン」列に試作プラン URL が書き込まれた
    sheet.write_trial_plan_url.assert_called_once()
    call_args = sheet.write_trial_plan_url.call_args
    assert call_args.args[0] == rows  # 行リスト
    assert "wf111" in call_args.args[1]  # URL or plan_id
