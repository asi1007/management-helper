from __future__ import annotations

from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet
from infrastructure.spreadsheet.sales_sheet import SalesSheet


def fill_missing_sku_fnsku(repo: BaseSheetsRepository, sheet: PurchaseSheet) -> None:
    sales = SalesSheet(repo)
    sheet.fill_missing_sku_fnsku_from_sales(sales.load_asin_to_sku_fnsku())
