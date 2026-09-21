import pytest

from usecases.sync_remarks import RemarkSyncPlan, build_remark_sync_plan


class Row:
    def __init__(self, row_number: int, asin: str, remark: str) -> None:
        self.row_number = row_number
        self._values = {"ASIN": asin, "備考": remark}

    def get(self, name: str) -> str:
        return self._values.get(name, "")


def test_備考が空の行に売上日の備考を入れる() -> None:
    plan = build_remark_sync_plan(
        [Row(255, "B0HJG1JTPT", "")], {"B0HJG1JTPT": "12*20cmのOPP袋に入れる"}
    )
    assert plan == [RemarkSyncPlan(255, "B0HJG1JTPT", "12*20cmのOPP袋に入れる")]


def test_既に備考がある行は触らない() -> None:
    """仕入管理の備考はロット別。同じ商品でも色・仕様が行ごとに違う
    （行189は磨砂、行190は透明）。上書きすると別ロットの指示が消える。"""
    plan = build_remark_sync_plan(
        [Row(189, "B0AAA", "帯卡位 磨砂")], {"B0AAA": "透明タイプ"}
    )
    assert plan == []


def test_overwriteなら既存も差し替える() -> None:
    plan = build_remark_sync_plan(
        [Row(189, "B0AAA", "帯卡位 磨砂")], {"B0AAA": "透明タイプ"}, overwrite=True
    )
    assert plan == [RemarkSyncPlan(189, "B0AAA", "透明タイプ")]


def test_同じ内容なら書かない() -> None:
    plan = build_remark_sync_plan(
        [Row(255, "B0AAA", "同じ文")], {"B0AAA": "同じ文"}, overwrite=True
    )
    assert plan == []


def test_売上日にも備考が無ければ対象外() -> None:
    assert build_remark_sync_plan([Row(255, "B0AAA", "")], {"B0AAA": ""}) == []


def test_売上日にASINが無ければ対象外() -> None:
    assert build_remark_sync_plan([Row(255, "B0AAA", "")], {}) == []


def test_ASINが空の行は対象外() -> None:
    assert build_remark_sync_plan([Row(255, "", "")], {"": "何か"}) == []


def test_行番号で絞れる() -> None:
    rows = [Row(255, "B0AAA", ""), Row(256, "B0BBB", "")]
    source = {"B0AAA": "A", "B0BBB": "B"}
    plan = build_remark_sync_plan(rows, source, row_numbers=[256])
    assert [p.row_number for p in plan] == [256]


def test_存在しない行番号を指定したら止める() -> None:
    with pytest.raises(ValueError, match="999"):
        build_remark_sync_plan([Row(255, "B0AAA", "")], {"B0AAA": "A"}, row_numbers=[999])
