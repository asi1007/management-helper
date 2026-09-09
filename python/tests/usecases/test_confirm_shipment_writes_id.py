from __future__ import annotations

from usecases.confirm_inbound_shipment import (
    SHIPMENT_SUMMARY_URL,
    _write_shipment_confirmation_id,
)


class _Row:
    def __init__(self, row_number: int) -> None:
        self.row_number = row_number


class _Sheet:
    def __init__(self) -> None:
        self.data = [_Row(179), _Row(185)]
        self._headers = ["備考", "ASIN", "納品プラン"]
        self.formulas: list[tuple[int, int, str]] = []
        self.cells: list[tuple[int, int, str]] = []

    def write_formula(self, row_num: int, column_num: int, formula: str) -> None:
        self.formulas.append((row_num, column_num, formula))

    def write_cell(self, row_num: int, column_num: int, value: str) -> None:
        self.cells.append((row_num, column_num, value))


class TestWriteShipmentConfirmationId:
    def test_全行にHYPERLINK数式を書く(self) -> None:
        sheet = _Sheet()
        _write_shipment_confirmation_id(sheet, "FBA15GHML0X3")
        assert [(r, c) for r, c, _ in sheet.formulas] == [(179, 3), (185, 3)]

    def test_リンク先はSellerCentralの納品詳細(self) -> None:
        sheet = _Sheet()
        _write_shipment_confirmation_id(sheet, "FBA15GHML0X3")
        formula = sheet.formulas[0][2]
        assert formula == (
            f'=HYPERLINK("{SHIPMENT_SUMMARY_URL}FBA15GHML0X3", "FBA15GHML0X3")'
        )

    def test_表示名は納品番号そのもの(self) -> None:
        sheet = _Sheet()
        _write_shipment_confirmation_id(sheet, "FBA15GHML0X3")
        assert '"FBA15GHML0X3")' in sheet.formulas[0][2]

    def test_URLにフラグメントを使わない(self) -> None:
        # 折り返しで切れると別ページが開くため # 以降にIDを置かない
        assert "#" not in SHIPMENT_SUMMARY_URL

    def test_FBA番号が空なら何も書かない(self) -> None:
        sheet = _Sheet()
        _write_shipment_confirmation_id(sheet, "")
        assert sheet.formulas == [] and sheet.cells == []

    def test_FBA形式でない値は書かない(self) -> None:
        sheet = _Sheet()
        _write_shipment_confirmation_id(sheet, "wf546a2b78")
        assert sheet.formulas == [] and sheet.cells == []

    def test_短すぎるFBA番号は書かない(self) -> None:
        sheet = _Sheet()
        _write_shipment_confirmation_id(sheet, "FBA123")
        assert sheet.formulas == [] and sheet.cells == []
