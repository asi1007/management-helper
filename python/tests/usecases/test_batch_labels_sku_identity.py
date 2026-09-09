from __future__ import annotations

import pytest

from usecases.batch_print_labels import _validate_sku_identity


class _Row:
    def __init__(self, row_number: int, asin: str, sku: str, fnsku: str) -> None:
        self.row_number = row_number
        self._d = {"ASIN": asin, "SKU": sku, "FNSKU": fnsku}

    def get(self, key: str) -> str:
        return self._d.get(key, "")


# SKU -> (ASIN, FNSKU)
CATALOG = {
    "LK-EMGO-63DL": ("B0G1J3NW6Y", "X001BZE9Q9"),
    "XM-ZLBK-D2DZ": ("B0F7R5WCPB", "X001AFD3G7"),
}


def _resolver(sku: str):
    return CATALOG.get(sku)


class TestValidateSkuIdentity:
    def test_ASINもFNSKUも一致していれば通る(self) -> None:
        rows = [_Row(215, "B0G1J3NW6Y", "LK-EMGO-63DL", "X001BZE9Q9")]
        _validate_sku_identity(rows, _resolver)

    def test_SKUが別商品を指していたらエラーで止める(self) -> None:
        rows = [_Row(215, "B0G1J3NW6Y", "XM-ZLBK-D2DZ", "X001BZE9Q9")]
        with pytest.raises(RuntimeError) as e:
            _validate_sku_identity(rows, _resolver)
        msg = str(e.value)
        assert "215" in msg and "XM-ZLBK-D2DZ" in msg and "B0F7R5WCPB" in msg

    def test_FNSKUが食い違っていたらエラーで止める(self) -> None:
        rows = [_Row(300, "B0G1J3NW6Y", "LK-EMGO-63DL", "X001AFD3G7")]
        with pytest.raises(RuntimeError, match="X001BZE9Q9"):
            _validate_sku_identity(rows, _resolver)

    def test_シートのFNSKUが空なら実物と照合せず通す(self) -> None:
        rows = [_Row(300, "B0G1J3NW6Y", "LK-EMGO-63DL", "")]
        _validate_sku_identity(rows, _resolver)

    def test_Amazonに存在しないSKUはエラーで止める(self) -> None:
        rows = [_Row(301, "B0XXXXXXXX", "NO-SUCH-SKU", "X001AAAAAA")]
        with pytest.raises(RuntimeError, match="NO-SUCH-SKU"):
            _validate_sku_identity(rows, _resolver)

    def test_不一致の行をすべて列挙する(self) -> None:
        rows = [
            _Row(215, "B0G1J3NW6Y", "XM-ZLBK-D2DZ", "X001BZE9Q9"),
            _Row(218, "B0G1J3NW6Y", "XM-ZLBK-D2DZ", "X001BZE9Q9"),
            _Row(220, "B0G1J3NW6Y", "LK-EMGO-63DL", "X001BZE9Q9"),
        ]
        with pytest.raises(RuntimeError) as e:
            _validate_sku_identity(rows, _resolver)
        msg = str(e.value)
        assert "215" in msg and "218" in msg
        assert "220" not in msg

    def test_同じSKUの照会は1回にまとめる(self) -> None:
        calls: list[str] = []

        def counting(sku: str):
            calls.append(sku)
            return CATALOG.get(sku)

        rows = [
            _Row(215, "B0G1J3NW6Y", "LK-EMGO-63DL", "X001BZE9Q9"),
            _Row(218, "B0G1J3NW6Y", "LK-EMGO-63DL", "X001BZE9Q9"),
        ]
        _validate_sku_identity(rows, counting)
        assert calls == ["LK-EMGO-63DL"]
