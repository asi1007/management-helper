from __future__ import annotations

from pathlib import Path

import pytest

from infrastructure.spreadsheet.instruction_sheet import InstructionSheet


PNG = (
    bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d4944415478da63fcffff3f0300050001aeb9c2ff0000000049454e44ae426082"
    )
    + b"\x00" * 4096
)


def _rows(*asins: str) -> list[dict[str, str]]:
    return [
        {
            "fnsku": f"X{i}",
            "asin": asin,
            "quantity": "10",
            "remarks": "",
            "order_number": "",
            "row_numbers": [10 + i],
        }
        for i, asin in enumerate(asins)
    ]


def _sheet(urls: dict[str, str | None], payloads: dict[str, bytes | None]) -> InstructionSheet:
    sheet = InstructionSheet(save_dir=Path("/tmp"), keepa_api_key="")
    sheet._resolve_image_url = lambda asin: urls.get(asin)  # type: ignore[method-assign]
    sheet._fetch_image_bytes = lambda url: payloads.get(url)  # type: ignore[method-assign]
    return sheet


class TestCollectImages:
    def test_全ASINで画像が取れたらASIN別のバイト列を返す(self) -> None:
        sheet = _sheet(
            urls={"B001": "http://img/1.jpg", "B002": "http://img/2.jpg"},
            payloads={"http://img/1.jpg": PNG, "http://img/2.jpg": PNG + b"\x00"},
        )
        assert sheet._collect_images(_rows("B001", "B002")) == {"B001": PNG, "B002": PNG + b"\x00"}

    def test_同じASINが複数行でも取得は1回にまとめる(self) -> None:
        calls: list[str] = []
        sheet = _sheet(urls={"B001": "http://img/1.jpg"}, payloads={"http://img/1.jpg": PNG})
        original = sheet._resolve_image_url

        def counting(asin: str) -> str | None:
            calls.append(asin)
            return original(asin)

        sheet._resolve_image_url = counting  # type: ignore[method-assign]
        assert sheet._collect_images(_rows("B001", "B001")) == {"B001": PNG}
        assert calls == ["B001"]

    def test_画像URLが取れないASINがあればエラーで止める(self) -> None:
        sheet = _sheet(
            urls={"B001": "http://img/1.jpg", "B002": None},
            payloads={"http://img/1.jpg": PNG},
        )
        with pytest.raises(RuntimeError, match="B002"):
            sheet._collect_images(_rows("B001", "B002"))

    def test_画像のダウンロードに失敗したASINがあればエラーで止める(self) -> None:
        sheet = _sheet(urls={"B001": "http://img/1.jpg"}, payloads={"http://img/1.jpg": None})
        with pytest.raises(RuntimeError, match="B001"):
            sheet._collect_images(_rows("B001"))

    def test_失敗したASINをすべて列挙する(self) -> None:
        sheet = _sheet(urls={"B001": None, "B002": None, "B003": "http://img/3.jpg"}, payloads={})
        with pytest.raises(RuntimeError) as excinfo:
            sheet._collect_images(_rows("B001", "B002", "B003"))
        message = str(excinfo.value)
        assert "B001" in message and "B002" in message and "B003" in message

    def test_ASINが空の行はエラーにする(self) -> None:
        sheet = _sheet(urls={}, payloads={})
        with pytest.raises(RuntimeError, match="ASIN"):
            sheet._collect_images(_rows(""))
