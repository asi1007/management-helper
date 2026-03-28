from __future__ import annotations

import logging

from shared.config import AppConfig
from infrastructure.amazon.auth import get_auth_token
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.home_shipment_sheet import HomeShipmentSheet
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet
from usecases.inbound_plan import create_inbound_plan

logger = logging.getLogger(__name__)


def create_inbound_plan_from_home_shipment(
    config: AppConfig, repo: BaseSheetsRepository, row_numbers: list[int]
) -> None:
    home_sheet = HomeShipmentSheet(repo, config.sheet_id, config.home_shipment_sheet_name)
    home_sheet.get_rows_by_numbers(row_numbers)
    purchase_row_numbers = home_sheet.get_row_numbers_column()
    if not purchase_row_numbers:
        raise RuntimeError("行番号が取得できません")
    purchase_sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    purchase_sheet.filter("行番号", purchase_row_numbers)
    purchase_row_nums = [r.row_number for r in purchase_sheet.data]
    create_inbound_plan(config, repo, purchase_row_nums)
