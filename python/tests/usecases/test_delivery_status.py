from __future__ import annotations

from datetime import date

from usecases.delivery_status import (
    StageReport,
    build_reports,
    elapsed_days,
    group_key_for,
)
from domain.shipment.delivery_stage import DeliveryStage


class _Row:
    def __init__(self, row_number: int, **kwargs) -> None:
        self.row_number = row_number
        self._d = {
            "ASIN": "B0TEST00001", "商品名": "商品", "購入数": "100",
            "購入日": "", "到着日": "", "梱包依頼日": "", "発送日": "", "受領日": "",
            "在庫数": "", "納品分類": "", "注文番号": "", "プラン別名": "", "納品プラン": "",
        }
        self._d.update({k: str(v) for k, v in kwargs.items()})

    def get(self, key, default=None):
        return self._d.get(key, default)


TODAY = date(2026, 9, 9)


class TestElapsedDays:
    def test_MMDD形式から経過日数を出す(self) -> None:
        assert elapsed_days("08-25", TODAY) == 15

    def test_スラッシュ区切りも読む(self) -> None:
        assert elapsed_days("08/25", TODAY) == 15

    def test_未来日は前年とみなす(self) -> None:
        # 「12-31」を今年扱いにすると経過日数が負になる
        assert elapsed_days("12-31", TODAY) > 0

    def test_読めない値はNone(self) -> None:
        assert elapsed_days("", TODAY) is None
        assert elapsed_days("未定", TODAY) is None


class TestGroupKeyFor:
    def test_イーウー待ちは注文番号でまとめる(self) -> None:
        row = _Row(10, 注文番号="Y0806-260729002")
        assert group_key_for(row, DeliveryStage.AWAITING_SUPPLIER) == "Y0806-260729002"

    def test_発送指示待ちは納品分類でまとめる(self) -> None:
        row = _Row(10, 到着日="09/09", 納品分類="ノーマル")
        assert group_key_for(row, DeliveryStage.AWAITING_SHIPMENT) == "ノーマル"

    def test_Amazon待ちはプラン別名でまとめる(self) -> None:
        row = _Row(10, 到着日="08/25", 発送日="09/10", プラン別名="08/25ノーマル")
        assert group_key_for(row, DeliveryStage.AWAITING_AMAZON) == "08/25ノーマル"

    def test_空なら未設定と表示する(self) -> None:
        assert group_key_for(_Row(10), DeliveryStage.AWAITING_SUPPLIER) == "(注文番号なし)"


class TestBuildReports:
    def test_3つの工程に振り分ける(self) -> None:
        rows = [
            _Row(1, 購入日="09-07"),
            _Row(2, 購入日="08-25", 到着日="08/28", 納品分類="ノーマル"),
            _Row(3, 購入日="08-01", 到着日="08/05", 発送日="09/01", プラン別名="08/25ノーマル"),
            _Row(4, 購入日="07-01", 到着日="07/05", 発送日="08/01", 受領日="08/10"),
        ]
        reports = build_reports(rows, today=TODAY)
        stages = {r.stage: r for r in reports}
        assert stages[DeliveryStage.AWAITING_SUPPLIER].row_count == 1
        assert stages[DeliveryStage.AWAITING_SHIPMENT].row_count == 1
        assert stages[DeliveryStage.AWAITING_AMAZON].row_count == 1
        assert DeliveryStage.DONE not in stages

    def test_数量を合計する(self) -> None:
        rows = [_Row(1, 購入数="200"), _Row(2, 購入数="300")]
        reports = build_reports(rows, today=TODAY)
        assert reports[0].total_quantity == 500

    def test_ASINが無い行は数えない(self) -> None:
        rows = [_Row(1, ASIN=""), _Row(2)]
        assert build_reports(rows, today=TODAY)[0].row_count == 1

    def test_経過日数の降順で並べる(self) -> None:
        rows = [_Row(1, 購入日="09-07"), _Row(2, 購入日="03-21"), _Row(3, 購入日="08-25")]
        entries = build_reports(rows, today=TODAY)[0].entries
        assert [e.row_number for e in entries] == [2, 3, 1]

    def test_工程は仕入から納品の順で返す(self) -> None:
        rows = [
            _Row(3, 到着日="08/05", 発送日="09/01"),
            _Row(1),
            _Row(2, 到着日="08/28"),
        ]
        reports = build_reports(rows, today=TODAY)
        assert [r.stage for r in reports] == [
            DeliveryStage.AWAITING_SUPPLIER,
            DeliveryStage.AWAITING_SHIPMENT,
            DeliveryStage.AWAITING_AMAZON,
        ]

    def test_該当が無い工程は返さない(self) -> None:
        assert [r.stage for r in build_reports([_Row(1)], today=TODAY)] == [
            DeliveryStage.AWAITING_SUPPLIER
        ]

    def test_滞留日数のしきい値を超えた件数を数える(self) -> None:
        rows = [_Row(1, 購入日="03-21"), _Row(2, 購入日="09-07")]
        report: StageReport = build_reports(rows, today=TODAY, stale_days=14)[0]
        assert report.stale_count == 1
