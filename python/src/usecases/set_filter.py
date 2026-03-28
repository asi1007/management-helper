from __future__ import annotations

import logging

from shared.config import AppConfig
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository

logger = logging.getLogger(__name__)


def set_filter(config: AppConfig, repo: BaseSheetsRepository) -> None:
    worksheet = repo.open_worksheet(config.sheet_id, config.purchase_sheet_name)
    filter_value = str(worksheet.cell(2, 5).value or "").strip()
    if not filter_value:
        logger.info("E2が空のためフィルタ設定をスキップ")
        return
    logger.info("フィルタ設定: %s", filter_value)
    logger.warning("gspreadではフィルタ設定機能が限定的です。手動設定を推奨します。")
