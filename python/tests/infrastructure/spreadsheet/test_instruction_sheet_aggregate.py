from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from src.infrastructure.spreadsheet.instruction_sheet import InstructionSheet


def _row(fnsku: str, sku: str, asin: str, qty: str, remarks: str = "", order: str = "", category: str = "テスト") -> SimpleNamespace:
    mapping = {
        "FNSKU": fnsku, "SKU": sku, "ASIN": asin, "購入数": qty,
        "備考": remarks, "注文番号": order, "納品分類": category,
    }
    return SimpleNamespace(get=lambda k, _m=mapping: _m.get(k))


def test_extract_rows_aggregates_same_sku():
    sheet = InstructionSheet(save_dir=Path("/tmp"), keepa_api_key="")
    data = [
        _row("X001AAA", "SKU-A", "BASIN1", "300", remarks="第1ロット", order="P001"),
        _row("X001AAA", "SKU-A", "BASIN1", "200", remarks="第2ロット", order="P002"),
        _row("X001BBB", "SKU-B", "BASIN2", "100", remarks="単独", order="P003"),
    ]
    rows = sheet._extract_rows(data)

    assert len(rows) == 2
    assert rows[0]["fnsku"] == "X001AAA"
    assert rows[0]["quantity"] == "500"
    assert "第1ロット" in rows[0]["remarks"]
    assert "第2ロット" in rows[0]["remarks"]
    assert "P001" in rows[0]["order_number"]
    assert "P002" in rows[0]["order_number"]
    assert rows[1]["fnsku"] == "X001BBB"
    assert rows[1]["quantity"] == "100"


def test_extract_rows_preserves_order():
    sheet = InstructionSheet(save_dir=Path("/tmp"), keepa_api_key="")
    data = [
        _row("X001BBB", "SKU-B", "BASIN2", "100"),
        _row("X001AAA", "SKU-A", "BASIN1", "300"),
        _row("X001BBB", "SKU-B", "BASIN2", "200"),
    ]
    rows = sheet._extract_rows(data)

    assert len(rows) == 2
    assert rows[0]["fnsku"] == "X001BBB"
    assert rows[0]["quantity"] == "300"
    assert rows[1]["fnsku"] == "X001AAA"


def test_extract_rows_falls_back_to_fnsku_when_sku_missing():
    sheet = InstructionSheet(save_dir=Path("/tmp"), keepa_api_key="")
    data = [
        _row("X001AAA", "", "BASIN1", "100"),
        _row("X001AAA", "", "BASIN1", "200"),
    ]
    rows = sheet._extract_rows(data)

    assert len(rows) == 1
    assert rows[0]["fnsku"] == "X001AAA"
    assert rows[0]["quantity"] == "300"


def test_extract_rows_skips_missing_fnsku():
    sheet = InstructionSheet(save_dir=Path("/tmp"), keepa_api_key="")
    data = [
        _row("", "SKU-A", "BASIN1", "100"),
        _row("X001AAA", "SKU-A", "BASIN1", "200"),
    ]
    rows = sheet._extract_rows(data)
    assert len(rows) == 1
    assert rows[0]["fnsku"] == "X001AAA"
    assert rows[0]["quantity"] == "200"


def test_extract_rows_deduplicates_identical_remarks_and_orders():
    sheet = InstructionSheet(save_dir=Path("/tmp"), keepa_api_key="")
    data = [
        _row("X001AAA", "SKU-A", "BASIN1", "100", remarks="同じ備考", order="P001"),
        _row("X001AAA", "SKU-A", "BASIN1", "200", remarks="同じ備考", order="P001"),
    ]
    rows = sheet._extract_rows(data)
    assert len(rows) == 1
    assert rows[0]["remarks"] == "同じ備考"
    assert rows[0]["order_number"] == "P001"
    assert rows[0]["quantity"] == "300"
