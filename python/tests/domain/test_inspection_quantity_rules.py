from __future__ import annotations

import pytest

from domain.shipment.inspection_quantity import (
    allocate_good_quantity,
    resolve_registered_quantity,
)


class TestResolveRegisteredQuantity:
    def test_良品数量が指示書より少なければ良品数量を採用(self) -> None:
        assert resolve_registered_quantity(instructed=1000, good=987) == 987

    def test_良品数量が指示書より多くても良品数量を採用(self) -> None:
        assert resolve_registered_quantity(instructed=1500, good=1561) == 1561

    def test_同数ならそのまま(self) -> None:
        assert resolve_registered_quantity(instructed=500, good=500) == 500

    def test_良品数量が負なら不正(self) -> None:
        with pytest.raises(ValueError):
            resolve_registered_quantity(instructed=500, good=-1)


class TestAllocateGoodQuantity:
    def test_単一行ならそのまま割り当てる(self) -> None:
        assert allocate_good_quantity([1000], 987) == [987]

    def test_複数行は先頭行から満たし不足を後ろの行で吸収する(self) -> None:
        assert allocate_good_quantity([500, 500], 988) == [500, 488]

    def test_超過分は最後の行に上乗せする(self) -> None:
        assert allocate_good_quantity([500, 500], 1061) == [500, 561]

    def test_先頭行を下回る場合は後ろの行が0になる(self) -> None:
        assert allocate_good_quantity([500, 500], 300) == [300, 0]

    def test_3行でも先頭から順に満たす(self) -> None:
        assert allocate_good_quantity([500, 500, 500], 1200) == [500, 500, 200]

    def test_合計が一致する(self) -> None:
        allocated = allocate_good_quantity([700, 300, 1000], 1850)
        assert sum(allocated) == 1850

    def test_行が無ければ空(self) -> None:
        assert allocate_good_quantity([], 100) == []
