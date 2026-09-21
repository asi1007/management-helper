import pytest

from infrastructure.spreadsheet.instruction_sheet import (
    REQUIRED_ROW_FIELDS,
    BlankInstructionFieldError,
    find_blank_fields,
)


def _row(**overrides) -> dict[str, str]:
    row = {
        "fnsku": "X001EJSTZJ",
        "asin": "B0HJG1JTPT",
        "quantity": "700",
        "remarks": "OPP袋に1個ずつ入れてFNSKUシールを貼る",
        "order_number": "Y0806-260911001",
        "row_numbers": [255],
    }
    row.update(overrides)
    return row


def test_全部埋まっていれば何も返さない() -> None:
    assert find_blank_fields([_row()]) == []


def test_備考が空なら検出する() -> None:
    """備考は梱包指示そのもの。空のまま出すと検品担当は梱包方法を知らされない。"""
    blanks = find_blank_fields([_row(remarks="")])
    assert blanks == [(255, ["備考"])]


def test_空白だけの備考も空とみなす() -> None:
    assert find_blank_fields([_row(remarks="   \n  ")]) == [(255, ["備考"])]


def test_注文番号が空なら検出する() -> None:
    assert find_blank_fields([_row(order_number="")]) == [(255, ["注文番号"])]


def test_数量0は空とみなす() -> None:
    assert find_blank_fields([_row(quantity="0")]) == [(255, ["数量"])]


def test_複数の欠けを1行にまとめて返す() -> None:
    blanks = find_blank_fields([_row(remarks="", order_number="")])
    assert blanks == [(255, ["備考", "注文番号"])]


def test_行番号順に返す() -> None:
    rows = [_row(row_numbers=[256], remarks=""), _row(row_numbers=[255], remarks="")]
    assert [n for n, _ in find_blank_fields(rows)] == [255, 256]


def test_行番号が無くても落ちない() -> None:
    assert find_blank_fields([_row(row_numbers=[], remarks="")]) == [(0, ["備考"])]


def test_検証する項目は指示書に書く列と一致する() -> None:
    assert set(REQUIRED_ROW_FIELDS) == {
        "fnsku",
        "asin",
        "quantity",
        "remarks",
        "order_number",
    }


def test_エラーには行番号と列名と直し方が載る() -> None:
    with pytest.raises(BlankInstructionFieldError) as e:
        raise BlankInstructionFieldError([(255, ["備考"]), (256, ["備考", "注文番号"])])
    message = str(e.value)
    assert "255" in message and "256" in message
    assert "備考" in message and "注文番号" in message
    assert "仕入管理" in message


class _SheetRow:
    def __init__(self, row_number: int, values: dict[str, str]) -> None:
        self.row_number = row_number
        self._values = values

    def get(self, name: str) -> str:
        return self._values.get(name, "")


def test_FNSKUが無い行は黙って消さずに検出する() -> None:
    """_extract_rows は FNSKU の無い行を読み飛ばすため、
    指示書からその商品が丸ごと抜けても誰も気づかない。"""
    from infrastructure.spreadsheet.instruction_sheet import find_dropped_rows

    rows = [
        _SheetRow(260, {"FNSKU": "", "ASIN": "B0HJWX3CDP", "購入数": "500"}),
        _SheetRow(255, {"FNSKU": "X001EJSTZJ", "ASIN": "B0HJG1JTPT", "購入数": "700"}),
    ]
    assert find_dropped_rows(rows) == [(260, ["FNSKU"])]


def test_全行にFNSKUがあれば何も返さない() -> None:
    from infrastructure.spreadsheet.instruction_sheet import find_dropped_rows

    rows = [_SheetRow(255, {"FNSKU": "X001EJSTZJ"})]
    assert find_dropped_rows(rows) == []
