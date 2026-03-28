from __future__ import annotations

import logging
from datetime import datetime

from shared.config import AppConfig
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.home_shipment_sheet import HomeShipmentSheet
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet

logger = logging.getLogger(__name__)


def update_arrival_date(config: AppConfig, repo: BaseSheetsRepository, row_numbers: list[int]) -> None:
    home_sheet = HomeShipmentSheet(repo, config.sheet_id, config.home_shipment_sheet_name)
    home_sheet.get_rows_by_numbers(row_numbers)
    tracking_numbers = home_sheet.get_values("追跡番号")
    if not tracking_numbers:
        raise RuntimeError("追跡番号が取得できません")
    purchase_sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    purchase_sheet.filter("追跡番号", tracking_numbers)
    today = datetime.now().strftime("%Y/%m/%d")
    purchase_sheet.write_column_by_func("自宅到着日", lambda _row, _i: today)
    logger.info("%d行の自宅到着日を更新しました", len(purchase_sheet.data))
