from __future__ import annotations

import pytest

from usecases.update_status_estimate import _is_target_row

PLAN_CELL = "FBA15GD8566V"
PLAN_FORMULA = '=HYPERLINK("https://sellercentral.amazon.co.jp/fba/sendtoamazon?wf=wfabc123&shipmentId=FBA15GD8566V","納品プラン")'


@pytest.mark.parametrize(
    "status",
    ["未発送", "梱包依頼必要", "梱包依頼済み", "発送済み", "自宅発送", "納品中", ""],
)
def test_納品プランがあれば状態に関わらず対象(status: str) -> None:
    assert _is_target_row(status, PLAN_CELL) is True


@pytest.mark.parametrize("status", ["在庫あり", "在庫なし"])
def test_受領後の状態はstockシート基準なので対象外(status: str) -> None:
    assert _is_target_row(status, PLAN_CELL) is False


@pytest.mark.parametrize("plan_cell", ["", "   ", "未定", "-"])
def test_納品プランに識別子がなければ対象外(plan_cell: str) -> None:
    assert _is_target_row("発送済み", plan_cell) is False


def test_HYPERLINK数式の納品プランも対象() -> None:
    assert _is_target_row("未発送", PLAN_FORMULA) is True


def test_状態の前後空白は無視される() -> None:
    assert _is_target_row("  在庫あり  ", PLAN_CELL) is False
