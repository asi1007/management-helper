from __future__ import annotations

import logging
import re
from typing import Any

import gspread
import httpx

from shared.config import AppConfig
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.inspection_master_repo import InspectionMasterRepo

logger = logging.getLogger(__name__)


def create_inspection_sheet_if_needed(
    config: AppConfig, repo: BaseSheetsRepository, drive_service: Any, rows: list[Any]
) -> str | None:
    if not config.inspection_master_sheet_id:
        return None
    asins = list({str(r.get("ASIN") or "").strip() for r in rows if r.get("ASIN")})
    if not asins:
        return None
    master_repo = InspectionMasterRepo(repo, config.inspection_master_sheet_id, config.inspection_master_sheet_gid)
    catalog = master_repo.load()
    filtered = catalog.filter_by_asins(asins)
    if filtered.size() == 0:
        logger.info("検品マスタに該当ASINなし -> スキップ")
        return None
    template_id = config.inspection_template_sheet_id
    if not template_id:
        return None
    copied = drive_service.files().copy(fileId=template_id, body={"name": "検品シート"}).execute()
    file_id = copied["id"]
    spreadsheet = repo.client.open_by_key(file_id)
    sheet = spreadsheet.sheet1
    row_num = 2
    for asin in filtered.asins():
        item = filtered.get(asin)
        if not item:
            continue
        sheet.update_cell(row_num, 1, item.asin)
        sheet.update_cell(row_num, 2, item.product_name)
        sheet.update_cell(row_num, 3, item.inspection_point)
        image_url = _get_product_image_url(asin, config.keepa_api_key)
        if image_url:
            cell_label = gspread.utils.rowcol_to_a1(row_num, 4)
            sheet.update_acell(cell_label, f'=IMAGE("{image_url}")')
        row_num += 1
    _append_detail_instruction_sheets(spreadsheet, filtered, repo)
    xlsx_url = f"https://docs.google.com/spreadsheets/d/{file_id}/export?format=xlsx"
    logger.info("検品シート作成: %s", xlsx_url)
    return xlsx_url


def _get_product_image_url(asin: str, keepa_api_key: str) -> str | None:
    if not keepa_api_key:
        return None
    try:
        url = f"https://api.keepa.com/product?key={keepa_api_key}&domain=5&asin={asin}"
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


def _append_detail_instruction_sheets(spreadsheet: Any, catalog: Any, repo: BaseSheetsRepository) -> None:
    for asin in catalog.asins():
        item = catalog.get(asin)
        if not item or not item.detail_instruction_url:
            continue
        parsed = _parse_spreadsheet_url(item.detail_instruction_url)
        if not parsed:
            continue
        try:
            source_ss = repo.client.open_by_key(parsed["spreadsheet_id"])
            if parsed.get("gid"):
                source_sheet = None
                for ws in source_ss.worksheets():
                    if str(ws.id) == str(parsed["gid"]):
                        source_sheet = ws
                        break
                if not source_sheet:
                    source_sheet = source_ss.sheet1
            else:
                source_sheet = source_ss.sheet1
            source_sheet.copy_to(spreadsheet.id)
            logger.info("詳細指示書シート追加: %s", asin)
        except Exception as e:
            logger.warning("詳細指示書コピー失敗 (%s): %s", asin, e)


def _parse_spreadsheet_url(url: str) -> dict[str, str] | None:
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    if not match:
        return None
    result: dict[str, str] = {"spreadsheet_id": match.group(1)}
    gid_match = re.search(r"gid=(\d+)", url)
    if gid_match:
        result["gid"] = gid_match.group(1)
    return result
