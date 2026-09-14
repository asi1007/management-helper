from __future__ import annotations

import io
import logging
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


class InstructionSheet:
    def __init__(self, save_dir: Path, keepa_api_key: str, access_token: str | None = None) -> None:
        self._save_dir = save_dir
        self._keepa_api_key = keepa_api_key
        self._access_token = access_token

    def create(self, data: list[Any], require_images: bool = True) -> Path:
        rows = self._extract_rows(data)
        plan_name = self._generate_plan_name(data)
        images = self._collect_images(rows, require_images=require_images)

        wb = load_workbook(str(TEMPLATE_PATH))
        ws = wb.active
        self._write_row_data(ws, rows, images)

        self._save_dir.mkdir(parents=True, exist_ok=True)
        file_path = self._save_dir / f"{plan_name}.xlsx"
        wb.save(str(file_path))
        logger.info("指示書保存: %s", file_path)
        return file_path

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
            else:
                aggregated[key] = {
                    "fnsku": fnsku,
                    "asin": asin,
                    "quantity": quantity,
                    "remarks_list": [remarks] if remarks else [],
                    "order_numbers": [order_number] if order_number else [],
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

    def _collect_images(
        self, rows: list[dict[str, str]], require_images: bool = True
    ) -> dict[str, bytes]:
        images: dict[str, bytes] = {}
        missing: list[str] = []
        for asin in self._unique_asins(rows):
            if not asin:
                missing.append("(ASIN空欄)")
                continue
            image = self._load_image(asin)
            if image is None:
                missing.append(asin)
                continue
            images[asin] = image
        if missing and not require_images:
            # 自宅発送は事務所へ送るだけで、FNSKUラベルも検品指示書も作らない。
            # 画像は現物照合のためのものなので、無くても作業は成立する。
            logger.warning("商品画像なしで指示書を作ります: %s", ", ".join(missing))
            return images
        if missing:
            raise RuntimeError(
                "指示書に載せる商品画像が取得できません: " + ", ".join(missing) +
                "。検品担当が現物と照合できないため中断しました。"
                "Amazonの商品ページに画像が登録されているか確認してください"
                "（新規出品直後はカタログに反映されるまで数時間かかります）。"
            )
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
