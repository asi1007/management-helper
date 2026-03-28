from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import gspread
import httpx

from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository

logger = logging.getLogger(__name__)

TEMPLATE_ID = "1qd3raNESIc35YvzPoBBwEKEFySDLw0-XZL9bNAcqcus"
START_ROW = 8


class InstructionSheet:
    def __init__(self, repo: BaseSheetsRepository, drive_service: Any, keepa_api_key: str) -> None:
        self._repo = repo
        self._drive_service = drive_service
        self._keepa_api_key = keepa_api_key

    def create(self, data: list[Any]) -> str:
        rows = self._extract_rows(data)
        plan_name = self._generate_plan_name(data)
        file_id, sheet = self._create_sheet_file(plan_name)
        self._write_row_data(sheet, rows)
        return f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"

    def _extract_rows(self, data: list[Any]) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for row in data:
            fnsku = str(row.get("FNSKU") or "").strip()
            asin = str(row.get("ASIN") or "").strip()
            product_name = str(row.get("商品名") or "").strip()
            quantity = str(row.get("購入数") or "").strip()
            if fnsku:
                rows.append({"fnsku": fnsku, "asin": asin, "product_name": product_name, "quantity": quantity})
        return rows

    def _generate_plan_name(self, data: list[Any]) -> str:
        now = datetime.now()
        date_str = f"{now.month:02d}/{now.day:02d}"
        try:
            category = str(data[0].get("納品分類") or "").strip() if data else ""
        except Exception:
            category = ""
        return f"{date_str}{category}指示書"

    def _create_sheet_file(self, plan_name: str) -> tuple[str, Any]:
        copied = self._drive_service.files().copy(fileId=TEMPLATE_ID, body={"name": plan_name}).execute()
        file_id = copied["id"]
        spreadsheet = self._repo.client.open_by_key(file_id)
        sheet = spreadsheet.sheet1
        return file_id, sheet

    def _write_row_data(self, sheet: Any, rows: list[dict[str, str]]) -> None:
        for i, row_data in enumerate(rows):
            row_num = START_ROW + i
            sheet.update_cell(row_num, 1, row_data["fnsku"])
            sheet.update_cell(row_num, 2, row_data["asin"])
            sheet.update_cell(row_num, 3, row_data["product_name"])
            sheet.update_cell(row_num, 4, row_data["quantity"])
            image_url = self._get_product_image(row_data["asin"])
            if image_url:
                cell_label = gspread.utils.rowcol_to_a1(row_num, 5)
                sheet.update_acell(cell_label, f'=IMAGE("{image_url}")')

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
            images_csv = products[0].get("imagesCSV", "")
            if not images_csv:
                return None
            first_image = images_csv.split(",")[0]
            return f"https://images-na.ssl-images-amazon.com/images/I/{first_image}._SL100_.jpg"
        except Exception as e:
            logger.warning("Keepa画像取得エラー (%s): %s", asin, e)
            return None
