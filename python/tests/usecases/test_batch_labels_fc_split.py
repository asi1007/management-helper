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


def test_check_fc_split_two_groups_raises(mocker):
    """2 packingGroups なら RuntimeError、行番号が表示される"""
    rows = [_row(340, "SKU_A"), _row(341, "SKU_B"), _row(342, "SKU_C")]
    groups = {"ノーマル": rows}
    sheet = mocker.Mock()
    packing_groups = [
        {"packingGroupId": "pg-aaa", "items": [{"msku": "SKU_A"}, {"msku": "SKU_B"}]},
        {"packingGroupId": "pg-bbb", "items": [{"msku": "SKU_C"}]},
    ]
    creator = _make_creator_mock(mocker, "wf222", packing_groups)

    with pytest.raises(RuntimeError, match=r"FC分割を検知"):
        _check_fc_split_for_all_groups(groups, creator, sheet)

    # 分割時は URL 書き込みなし
    sheet.write_trial_plan_url.assert_not_called()


def test_check_fc_split_report_contains_row_numbers(mocker, capsys):
    """分割時に各グループのSKUと行番号が表示される"""
    rows = [_row(340, "SKU_A"), _row(341, "SKU_B"), _row(342, "SKU_C")]
    groups = {"ノーマル": rows}
    sheet = mocker.Mock()
    packing_groups = [
        {"packingGroupId": "pg-aaa", "items": [{"msku": "SKU_A"}, {"msku": "SKU_B"}]},
        {"packingGroupId": "pg-bbb", "items": [{"msku": "SKU_C"}]},
    ]
    creator = _make_creator_mock(mocker, "wf333", packing_groups)

    with pytest.raises(RuntimeError):
        _check_fc_split_for_all_groups(groups, creator, sheet)

    captured = capsys.readouterr()
    out = captured.err + captured.out
    assert "ノーマル" in out
    assert "wf333" in out
    assert "340" in out
    assert "341" in out
    assert "342" in out
    assert "pg-aaa" in out
    assert "pg-bbb" in out


def test_check_fc_split_multiple_groups_split(mocker, capsys):
    """複数グループそれぞれが分割した場合、両方のサマリーが表示される"""
    rows_n = [_row(340, "N_A"), _row(341, "N_B")]
    rows_f = [_row(350, "F_A"), _row(351, "F_B")]
    groups = {"ノーマル": rows_n, "ファッション": rows_f}
    sheet = mocker.Mock()

    creator = mocker.Mock()
    creator.create_plan.side_effect = [
        {"inboundPlanId": "wfN1", "link": "url-N"},
        {"inboundPlanId": "wfF1", "link": "url-F"},
    ]
    creator.get_packing_groups.side_effect = [
        [
            {"packingGroupId": "pg-n1", "items": [{"msku": "N_A"}]},
            {"packingGroupId": "pg-n2", "items": [{"msku": "N_B"}]},
        ],
        [
            {"packingGroupId": "pg-f1", "items": [{"msku": "F_A"}]},
            {"packingGroupId": "pg-f2", "items": [{"msku": "F_B"}]},
        ],
    ]

    with pytest.raises(RuntimeError, match=r"2グループ"):
        _check_fc_split_for_all_groups(groups, creator, sheet)

    captured = capsys.readouterr()
    out = captured.err + captured.out
    assert "ノーマル" in out
    assert "ファッション" in out
    assert "wfN1" in out
    assert "wfF1" in out


def test_check_fc_split_partial_split_blocks_all_writes(mocker, capsys):
    """グループA: 1個 OK, グループB: 2個分割 → 全グループ停止、A の URL も書き込まれない"""
    rows_a = [_row(340, "A_1")]
    rows_b = [_row(350, "B_1"), _row(351, "B_2")]
    groups = {"ノーマル": rows_a, "ファッション": rows_b}
    sheet = mocker.Mock()

    creator = mocker.Mock()
    creator.create_plan.side_effect = [
        {"inboundPlanId": "wfA", "link": "url-A"},
        {"inboundPlanId": "wfB", "link": "url-B"},
    ]
    creator.get_packing_groups.side_effect = [
        [{"packingGroupId": "pg-a", "items": [{"msku": "A_1"}]}],
        [
            {"packingGroupId": "pg-b1", "items": [{"msku": "B_1"}]},
            {"packingGroupId": "pg-b2", "items": [{"msku": "B_2"}]},
        ],
    ]

    with pytest.raises(RuntimeError, match=r"1グループ"):
        _check_fc_split_for_all_groups(groups, creator, sheet)

    sheet.write_trial_plan_url.assert_not_called()
    captured = capsys.readouterr()
    out = captured.err + captured.out
    assert "ファッション" in out
    # ノーマルは分割していないので明示的に[ノーマル]の試作プラン報告は出ない


def test_batch_print_labels_invokes_fc_split_check(mocker):
    """batch_print_labels の処理順序で _check_fc_split_for_all_groups が呼ばれる"""
    from src.usecases import batch_print_labels as mod

    # SP-API auth と sheet を mock
    mocker.patch.object(mod, "get_auth_token", return_value="token")

    # PurchaseSheet を mock。filter後 1グループ分のデータが返る想定
    rows = [_row(340, "SKU_A"), _row(341, "SKU_B")]
    mock_sheet_cls = mocker.patch.object(mod, "PurchaseSheet")
    mock_sheet = mock_sheet_cls.return_value
    mock_sheet.data = rows

    # SKU/FNSKU 補完は usecases.sku_completion に集約されているのでそこをパッチ
    mocker.patch.object(mod, "fill_missing_sku_fnsku")

    # InboundPlanCreator を mock (FC分割なし)
    mock_creator_cls = mocker.patch.object(mod, "InboundPlanCreator")
    mock_creator_cls.return_value.create_plan.return_value = {
        "inboundPlanId": "wfX", "link": "url-X"
    }
    mock_creator_cls.return_value.get_packing_groups.return_value = [{"packingGroupId": "pg-x"}]

    # ラベル生成以降は実行しないように short-circuit
    mocker.patch.object(mod, "_create_label_pdf", return_value=[])
    mocker.patch.object(mod, "_create_instruction_sheet", return_value=Path("/tmp/dummy.xlsx"))
    mocker.patch.object(mod, "_create_inspection_sheet", return_value=None)
    mocker.patch.object(mod, "_write_to_sheet")
    mocker.patch.object(mod, "_send_chatwork_by_group")
    mocker.patch.object(mod, "_print_summary")

    config = mocker.Mock()
    config.chatwork_api_token = None
    config.chatwork_room_id = None
    repo = mocker.Mock()

    mod.batch_print_labels(config, repo, category_filter=["ノーマル"])

    # FC分割チェックが create_plan を呼んだことを確認
    mock_creator_cls.return_value.create_plan.assert_called_once()
    mock_creator_cls.return_value.get_packing_groups.assert_called_once()
    # OK だったので write_trial_plan_url が呼ばれる
    mock_sheet.write_trial_plan_url.assert_called_once()
