import pytest

from usecases.batch_print_labels import select_rows_by_number


class Row:
    def __init__(self, row_number: int) -> None:
        self.row_number = row_number


def test_指定した行番号だけを残す() -> None:
    rows = [Row(255), Row(256), Row(257)]
    assert [r.row_number for r in select_rows_by_number(rows, [255, 257])] == [255, 257]


def test_行番号を指定しなければ全行を返す() -> None:
    rows = [Row(255), Row(256)]
    assert select_rows_by_number(rows, None) == rows


def test_存在しない行番号を指定したら止める() -> None:
    """梱包依頼必要でない行を渡しても黙って空振りさせない。
    行番号は archive-out-of-stock で毎日ずれるので、指定ミスを事故扱いする。"""
    with pytest.raises(ValueError, match="261"):
        select_rows_by_number([Row(255)], [255, 261])


def test_全部が対象外なら止める() -> None:
    with pytest.raises(ValueError, match="999"):
        select_rows_by_number([Row(255)], [999])
