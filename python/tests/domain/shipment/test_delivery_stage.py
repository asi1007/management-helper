from __future__ import annotations

import pytest

from domain.shipment.delivery_stage import DeliveryStage, classify_stage


def _row(**kwargs) -> dict[str, str]:
    base = {"ASIN": "B0TEST00001", "到着日": "", "梱包依頼日": "", "発送日": "", "受領日": "", "在庫数": "", "納品分類": ""}
    base.update(kwargs)
    return base


class TestClassifyStage:
    def test_到着日が空ならイーウー到着待ち(self) -> None:
        assert classify_stage(_row()) is DeliveryStage.AWAITING_SUPPLIER

    def test_到着済みで発送前なら発送指示待ち(self) -> None:
        assert classify_stage(_row(到着日="09/09")) is DeliveryStage.AWAITING_SHIPMENT

    def test_梱包依頼済みでもまだ発送指示待ち(self) -> None:
        row = _row(到着日="09/09", 梱包依頼日="09/09")
        assert classify_stage(row) is DeliveryStage.AWAITING_SHIPMENT

    def test_発送済みで未受領ならAmazon倉庫到着待ち(self) -> None:
        row = _row(到着日="08/25", 梱包依頼日="08/25", 発送日="09/10")
        assert classify_stage(row) is DeliveryStage.AWAITING_AMAZON

    def test_受領日が入っていれば完了(self) -> None:
        row = _row(到着日="08/25", 梱包依頼日="08/25", 発送日="09/10", 受領日="09/20")
        assert classify_stage(row) is DeliveryStage.DONE

    def test_在庫数が入っていれば受領済みとみなす(self) -> None:
        # 受領日が未記入でも在庫が立っていれば Amazon に入っている
        row = _row(到着日="08/25", 梱包依頼日="08/25", 発送日="09/10", 在庫数="500")
        assert classify_stage(row) is DeliveryStage.DONE

    def test_在庫数ゼロも受領済み扱い(self) -> None:
        row = _row(到着日="08/25", 発送日="09/10", 在庫数="0")
        assert classify_stage(row) is DeliveryStage.DONE

    def test_自宅発送は発送日が入るまで発送指示待ち(self) -> None:
        row = _row(到着日="08/25", 梱包依頼日="08/25", 納品分類="自宅")
        assert classify_stage(row) is DeliveryStage.AWAITING_SHIPMENT

    def test_ASINが無い行は対象外(self) -> None:
        assert classify_stage(_row(ASIN="")) is None

    def test_空白だけの値は未入力として扱う(self) -> None:
        assert classify_stage(_row(到着日="   ")) is DeliveryStage.AWAITING_SUPPLIER

    def test_状態列は判定に使わない(self) -> None:
        # 状態は他列から導出される数式なので入力条件にしない
        row = _row(到着日="09/09", 状態="在庫あり")
        assert classify_stage(row) is DeliveryStage.AWAITING_SHIPMENT


class TestStageOrder:
    def test_工程の並び順は仕入から納品へ(self) -> None:
        order = [s for s in DeliveryStage]
        assert order.index(DeliveryStage.AWAITING_SUPPLIER) < order.index(DeliveryStage.AWAITING_SHIPMENT)
        assert order.index(DeliveryStage.AWAITING_SHIPMENT) < order.index(DeliveryStage.AWAITING_AMAZON)

    def test_各段階に日本語の見出しがある(self) -> None:
        for stage in DeliveryStage:
            assert stage.label
