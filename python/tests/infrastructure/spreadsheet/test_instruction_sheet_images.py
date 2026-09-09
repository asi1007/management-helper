from __future__ import annotations

from pathlib import Path

import pytest

from infrastructure.spreadsheet.instruction_sheet import InstructionSheet


def _rows(*asins: str) -> list[dict[str, str]]:
    return [
        {"fnsku": f"X{i}", "asin": asin, "quantity": "10", "remarks": "", "order_number": ""}
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
            payloads={"http://img/1.jpg": b"one", "http://img/2.jpg": b"two"},
        )
        assert sheet._collect_images(_rows("B001", "B002")) == {"B001": b"one", "B002": b"two"}

    def test_同じASINが複数行でも取得は1回にまとめる(self) -> None:
        calls: list[str] = []
        sheet = _sheet(urls={"B001": "http://img/1.jpg"}, payloads={"http://img/1.jpg": b"one"})
        original = sheet._resolve_image_url

        def counting(asin: str) -> str | None:
            calls.append(asin)
            return original(asin)

        sheet._resolve_image_url = counting  # type: ignore[method-assign]
        assert sheet._collect_images(_rows("B001", "B001")) == {"B001": b"one"}
        assert calls == ["B001"]

    def test_画像URLが取れないASINがあればエラーで止める(self) -> None:
        sheet = _sheet(
            urls={"B001": "http://img/1.jpg", "B002": None},
            payloads={"http://img/1.jpg": b"one"},
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
