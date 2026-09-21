from __future__ import annotations

import io
import logging
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from openpyxl import load_workbook
from openpyxl.drawing.image import Image as XlImage

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "instruction_template.xlsx"
START_ROW = 8
MARKETPLACE_ID = "A1VC38T7YXB528"
CATALOG_ENDPOINT = "https://sellingpartnerapi-fe.amazon.com/catalog/2022-04-01/items"
MAIN_IMAGE_VARIANT = "MAIN"


# 指示書に書く列。ここが空のまま渡すと検品担当が判断できないので出さずに止める。
# キーは _extract_rows が返す辞書のキー、値は人が見る列名。
REQUIRED_ROW_FIELDS: dict[str, str] = {
    "fnsku": "FNSKU",
    "asin": "ASIN",
    "quantity": "数量",
    "remarks": "備考",
    "order_number": "注文番号",
}


class BlankInstructionFieldError(RuntimeError):
    def __init__(self, blanks: list[tuple[int, list[str]]]) -> None:
        lines = [f"  行{row_number}: {'・'.join(names)}" for row_number, names in blanks]
        super().__init__(
            "指示書に空欄のまま出せない項目があります。仕入管理シートを埋めてから実行してください。\n"
            + "\n".join(lines)
            + "\n  備考が空なら梱包方法が未決定です（/suggest-packing で決めて備考へ書く）"
        )


# 指示書に載せられる画像。Amazon のカタログ画像は jpg / png で返る。
# GIF を除いているのは images-na.ssl-images-amazon.com が
# 画像の無い ASIN に対して 200 と 43 バイトの透明 GIF を返すため。
IMAGE_SIGNATURES: tuple[bytes, ...] = (
    b"\x89PNG\r\n\x1a\n",
    b"\xff\xd8\xff",
)
# 商品写真として成立する最小バイト数。実際のカタログ画像は数十 KB あり、
# これを下回るものは 1px のダミーか壊れた断片で、貼っても現物照合に使えない。
MIN_IMAGE_BYTES = 1024


class MissingProductImageError(RuntimeError):
    def __init__(self, missing: list[tuple[int, str]], reason: str) -> None:
        lines = [f"  行{row_number}: {asin or '(ASIN空欄)'}" for row_number, asin in missing]
        super().__init__(
            f"指示書に商品写真が{reason}。検品担当が現物と照合できないため中断しました。\n"
            + "\n".join(lines)
            + "\n  Amazonの商品ページに画像が登録されているか確認してください"
            "（新規出品直後はカタログに反映されるまで数時間かかります）。"
        )


def is_usable_product_image(payload: bytes | None) -> bool:
    if not payload or len(payload) < MIN_IMAGE_BYTES:
        return False
    return payload.startswith(IMAGE_SIGNATURES)


def find_rows_without_image(
    rows: list[dict[str, Any]], images: dict[str, bytes]
) -> list[tuple[int, str]]:
    missing: list[tuple[int, str]] = []
    for row in rows:
        asin = str(row.get("asin") or "")
        if asin and asin in images:
            continue
        missing.append((min(row.get("row_numbers") or [0]), asin))
    missing.sort(key=lambda item: item[0])
    return missing


def count_embedded_images(file_path: Path) -> int:
    with zipfile.ZipFile(str(file_path)) as archive:
        return len([name for name in archive.namelist() if name.startswith("xl/media/")])


def template_image_count() -> int:
    return count_embedded_images(TEMPLATE_PATH)


def _is_blank(field: str, value: Any) -> bool:
    text = str(value or "").strip()
    if field == "quantity":
        return text in ("", "0")
    return not text


def find_dropped_rows(data: list[Any]) -> list[tuple[int, list[str]]]:
    """FNSKU が無く指示書から読み飛ばされる行を返す。

    _extract_rows は FNSKU の無い行を黙って捨てるため、
    その商品が指示書から丸ごと抜けても空欄すら残らず気づけない。
    """
    dropped = [
        (getattr(row, "row_number", 0), [REQUIRED_ROW_FIELDS["fnsku"]])
        for row in data
        if not str(row.get("FNSKU") or "").strip()
    ]
    dropped.sort(key=lambda item: item[0])
    return dropped


def find_blank_fields(rows: list[dict[str, Any]]) -> list[tuple[int, list[str]]]:
    """指示書に書く項目のうち空のものを (行番号, 列名) で返す"""
    blanks: list[tuple[int, list[str]]] = []
    for row in rows:
        missing = [
            label for field, label in REQUIRED_ROW_FIELDS.items() if _is_blank(field, row.get(field))
        ]
        if not missing:
            continue
        row_numbers = row.get("row_numbers") or [0]
        blanks.append((min(row_numbers), missing))
    blanks.sort(key=lambda item: item[0])
    return blanks


class InstructionSheet:
    def __init__(self, save_dir: Path, keepa_api_key: str, access_token: str | None = None) -> None:
        self._save_dir = save_dir
        self._keepa_api_key = keepa_api_key
        self._access_token = access_token

    def create(self, data: list[Any]) -> Path:
        rows = self._extract_rows(data)
        blanks = find_dropped_rows(data) + find_blank_fields(rows)
        if blanks:
            raise BlankInstructionFieldError(sorted(blanks, key=lambda item: item[0]))
        plan_name = self._generate_plan_name(data)
        images = self._collect_images(rows)

        wb = load_workbook(str(TEMPLATE_PATH))
        ws = wb.active
        self._write_row_data(ws, rows, images)

        self._save_dir.mkdir(parents=True, exist_ok=True)
        file_path = self._save_dir / f"{plan_name}.xlsx"
        wb.save(str(file_path))
        self._verify_images_embedded(file_path, rows)
        logger.info("指示書保存: %s", file_path)
        return file_path

    def _verify_images_embedded(self, file_path: Path, rows: list[dict[str, str]]) -> None:
        # 画像を取れていても貼り付けに失敗すれば写真の無い指示書ができるので、
        # 保存したファイル自身に何枚入ったかで確かめる。
        embedded = count_embedded_images(file_path) - template_image_count()
        if embedded >= len(rows):
            return
        file_path.unlink(missing_ok=True)
        raise MissingProductImageError(
            [(min(row.get("row_numbers") or [0]), str(row.get("asin") or "")) for row in rows],
            f"置かれていません（{len(rows)}件に対し{max(embedded, 0)}枚）",
        )

    def _extract_rows(self, data: list[Any]) -> list[dict[str, str]]:
        aggregated: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        for row in data:
            fnsku = str(row.get("FNSKU") or "").strip()
            if not fnsku:
                continue
            sku = str(row.get("SKU") or "").strip()
            asin = str(row.get("ASIN") or "").strip()
            quantity_str = str(row.get("購入数") or "").strip()
            try:
                quantity = int(quantity_str) if quantity_str else 0
            except ValueError:
                quantity = 0
            remarks = str(row.get("備考") or "").strip()
            order_number = str(row.get("注文番号") or "").strip()

            key = sku or fnsku
            if key in aggregated:
                agg = aggregated[key]
                agg["quantity"] += quantity
                if remarks and remarks not in agg["remarks_list"]:
                    agg["remarks_list"].append(remarks)
                if order_number and order_number not in agg["order_numbers"]:
                    agg["order_numbers"].append(order_number)
                agg["row_numbers"].append(getattr(row, "row_number", 0))
            else:
                aggregated[key] = {
                    "fnsku": fnsku,
                    "asin": asin,
                    "quantity": quantity,
                    "remarks_list": [remarks] if remarks else [],
                    "order_numbers": [order_number] if order_number else [],
                    "row_numbers": [getattr(row, "row_number", 0)],
                }
                order.append(key)

        rows: list[dict[str, str]] = []
        for key in order:
            agg = aggregated[key]
            rows.append({
                "fnsku": agg["fnsku"],
                "asin": agg["asin"],
                "quantity": str(agg["quantity"]),
                "remarks": "\n".join(agg["remarks_list"]),
                "order_number": ", ".join(agg["order_numbers"]),
                "row_numbers": agg["row_numbers"],
            })
        return rows

    def _generate_plan_name(self, data: list[Any]) -> str:
        now = datetime.now()
        date_str = f"{now.month:02d}{now.day:02d}"
        try:
            category = str(data[0].get("納品分類") or "").strip() if data else ""
        except Exception:
            category = ""
        return f"{date_str}{category}指示書"

    def _write_row_data(self, ws: Any, rows: list[dict[str, str]], images: dict[str, bytes]) -> None:
        for i, row_data in enumerate(rows):
            row_num = START_ROW + i
            # B列: FNSKU, C列: ASIN, D列: 数量（テンプレートの列順に合わせる）
            ws.cell(row=row_num, column=2, value=row_data["fnsku"])
            ws.cell(row=row_num, column=3, value=row_data["asin"])
            ws.cell(row=row_num, column=4, value=int(row_data["quantity"]) if row_data["quantity"] else 0)
            ws.cell(row=row_num, column=5, value=row_data["remarks"])
            ws.cell(row=row_num, column=6, value=row_data["order_number"])

            image = images.get(row_data["asin"])
            if image is None:
                continue
            img = XlImage(io.BytesIO(image))
            img.width = 75
            img.height = 75
            ws.add_image(img, f"A{row_num}")

    def _collect_images(self, rows: list[dict[str, str]]) -> dict[str, bytes]:
        images: dict[str, bytes] = {}
        for asin in self._unique_asins(rows):
            if not asin:
                continue
            image = self._load_image(asin)
            if not is_usable_product_image(image):
                logger.warning("商品写真として使えません: ASIN=%s", asin)
                continue
            images[asin] = image
        missing = find_rows_without_image(rows, images)
        if missing:
            raise MissingProductImageError(missing, "入っていません")
        return images

    def _unique_asins(self, rows: list[dict[str, str]]) -> list[str]:
        seen: list[str] = []
        for row_data in rows:
            asin = str(row_data.get("asin") or "").strip()
            if asin not in seen:
                seen.append(asin)
        return seen

    def _load_image(self, asin: str) -> bytes | None:
        image_url = self._resolve_image_url(asin)
        if not image_url:
            return None
        return self._fetch_image_bytes(image_url)

    def _resolve_image_url(self, asin: str) -> str | None:
        return self._get_product_image(asin) or self._get_catalog_image(asin)

    def _fetch_image_bytes(self, image_url: str) -> bytes | None:
        try:
            response = httpx.get(image_url, timeout=10.0)
        except Exception as e:
            logger.warning("画像ダウンロードエラー (%s): %s", image_url, e)
            return None
        if response.status_code != 200 or not response.content:
            logger.warning("画像ダウンロード失敗 (%s): HTTP %s", image_url, response.status_code)
            return None
        return response.content

    def _get_catalog_image(self, asin: str) -> str | None:
        if not asin or not self._access_token:
            return None
        try:
            response = httpx.get(
                f"{CATALOG_ENDPOINT}/{asin}",
                params={"marketplaceIds": MARKETPLACE_ID, "includedData": "images"},
                headers={"Accept": "application/json", "x-amz-access-token": self._access_token},
                timeout=30.0,
            )
            response.raise_for_status()
            for image_set in response.json().get("images") or []:
                for image in image_set.get("images") or []:
                    if image.get("variant") == MAIN_IMAGE_VARIANT and image.get("link"):
                        return str(image["link"])
            return None
        except Exception as e:
            logger.warning("カタログ画像取得エラー (%s): %s", asin, e)
            return None

    def _get_product_image(self, asin: str) -> str | None:
        if not asin or not self._keepa_api_key:
            return None
        try:
            url = f"https://api.keepa.com/product?key={self._keepa_api_key}&domain=5&asin={asin}"
            response = httpx.get(url, timeout=30.0)
            data = response.json()
            products = data.get("products", [])
            if not products:
                return None
            product = products[0]
            images_csv = product.get("imagesCSV", "")
            if images_csv:
                first_image = images_csv.split(",")[0]
                return f"https://images-na.ssl-images-amazon.com/images/I/{first_image}._SL100_.jpg"
            images = product.get("images", [])
            if images:
                image_id = images[0].get("m") or images[0].get("l", "")
                if image_id:
                    return f"https://images-na.ssl-images-amazon.com/images/I/{image_id}"
            return None
        except Exception as e:
            logger.warning("Keepa画像取得エラー (%s): %s", asin, e)
            return None
