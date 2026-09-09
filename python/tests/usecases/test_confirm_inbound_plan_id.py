from __future__ import annotations

import pytest

from usecases.confirm_inbound_shipment import _resolve_inbound_plan_id

FULL_ID = "wf545a35b7-aa49-42e3-93e3-5a36fa84a5f2"
SHORT_ID = "wf545a35b7"
HYPERLINK = (
    '=HYPERLINK("https://sellercentral.amazon.co.jp/fba/sendtoamazon/'
    f'confirm_content_step?wf={FULL_ID}","{SHORT_ID}")'
)


class _FakeRow:
    def __init__(self, display: str, row_number: int = 200) -> None:
        self._display = display
        self.row_number = row_number

    def get(self, column_name: str) -> str:
        assert column_name == "納品プラン"
        return self._display


class _FakeSheet:
    def __init__(self, display: str, formula: str) -> None:
        self.data = [_FakeRow(display)]
        self._formula = formula
        self.asked: list[tuple[int, str]] = []

    def read_cell_formula(self, row_number: int, column_name: str) -> str:
        self.asked.append((row_number, column_name))
        return self._formula


class TestResolveInboundPlanId:
    def test_表示値が短縮IDなら数式のURLからフルIDを取る(self) -> None:
        sheet = _FakeSheet(display=SHORT_ID, formula=HYPERLINK)
        assert _resolve_inbound_plan_id(sheet) == FULL_ID
        assert sheet.asked == [(200, "納品プラン")]

    def test_表示値がフルIDならそのまま使い数式は読まない(self) -> None:
        sheet = _FakeSheet(display=FULL_ID, formula="")
        assert _resolve_inbound_plan_id(sheet) == FULL_ID
        assert sheet.asked == []

    def test_数式にもフルIDが無ければ短縮IDのまま進めずエラー(self) -> None:
        sheet = _FakeSheet(display=SHORT_ID, formula=SHORT_ID)
        with pytest.raises(RuntimeError, match="短縮"):
            _resolve_inbound_plan_id(sheet)

    def test_納品プラン列が空ならエラー(self) -> None:
        sheet = _FakeSheet(display="", formula="")
        with pytest.raises(RuntimeError, match="取得できません"):
            _resolve_inbound_plan_id(sheet)

    def test_行が無ければエラー(self) -> None:
        sheet = _FakeSheet(display="", formula="")
        sheet.data = []
        with pytest.raises(RuntimeError, match="取得できません"):
            _resolve_inbound_plan_id(sheet)
