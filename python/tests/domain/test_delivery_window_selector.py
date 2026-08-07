from __future__ import annotations

from datetime import date

import pytest

from domain.shipment.delivery_window_selector import (
    add_months,
    select_delivery_window_option_id,
)


def _option(option_id: str, start: str, availability: str = "AVAILABLE") -> dict[str, object]:
    return {
        "deliveryWindowOptionId": option_id,
        "startDate": f"{start}T00:00Z",
        "endDate": f"{start}T00:00Z",
        "availabilityType": availability,
    }


class TestAddMonths:
    def test_同月内の単純な加算(self) -> None:
        assert add_months(date(2026, 8, 6), 1) == date(2026, 9, 6)

    def test_年をまたぐ加算(self) -> None:
        assert add_months(date(2026, 12, 15), 1) == date(2027, 1, 15)

    def test_月末日は翌月の末日に丸める(self) -> None:
        assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)


class TestSelectDeliveryWindowOptionId:
    def test_出荷日の1ヶ月後に最も近いウィンドウを選ぶ(self) -> None:
        options = [
            _option("dw-0805", "2026-08-05"),
            _option("dw-0831", "2026-08-31"),
            _option("dw-0906", "2026-09-06"),
            _option("dw-0917", "2026-09-17"),
        ]
        assert select_delivery_window_option_id(options, ship_date=date(2026, 8, 6)) == "dw-0906"

    def test_完全一致がなければ最も近い日付を選ぶ(self) -> None:
        options = [_option("dw-0904", "2026-09-04"), _option("dw-0909", "2026-09-09")]
        assert select_delivery_window_option_id(options, ship_date=date(2026, 8, 6)) == "dw-0904"

    def test_利用不可のウィンドウは選ばない(self) -> None:
        options = [
            _option("dw-0906", "2026-09-06", availability="UNAVAILABLE"),
            _option("dw-0910", "2026-09-10"),
        ]
        assert select_delivery_window_option_id(options, ship_date=date(2026, 8, 6)) == "dw-0910"

    def test_リードタイムを日数で上書きできる(self) -> None:
        options = [_option("dw-0813", "2026-08-13"), _option("dw-0906", "2026-09-06")]
        selected = select_delivery_window_option_id(
            options, ship_date=date(2026, 8, 6), lead_days=7
        )
        assert selected == "dw-0813"

    def test_候補が空ならエラー(self) -> None:
        with pytest.raises(RuntimeError, match="配送ウィンドウ"):
            select_delivery_window_option_id([], ship_date=date(2026, 8, 6))
