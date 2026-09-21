from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any, Mapping, Protocol, Sequence

from domain.inventory.value_objects.launch_ready_product import (
    ASIN_COLUMN,
    INVENTORY_COLUMN,
    PRODUCT_NAME_COLUMN,
    PURCHASE_COUNT_COLUMN,
    RECEIVED_DATE_COLUMN,
    LaunchReadyProduct,
    collect_launch_ready_products,
)
from infrastructure.spreadsheet.base_sheets_repository import BaseSheetsRepository
from infrastructure.spreadsheet.purchase_sheet import PurchaseSheet
from infrastructure.store.notified_asin_store import NotifiedAsinStore
from infrastructure.todoist.launch_ready_notifier import LaunchReadyNotifier
from shared.config import AppConfig

logger = logging.getLogger(__name__)

NOTIFIED_STORE_PATH = Path(__file__).resolve().parents[2] / ".launch_ready_notified.json"
READ_COLUMNS = (
    ASIN_COLUMN,
    PRODUCT_NAME_COLUMN,
    PURCHASE_COUNT_COLUMN,
    RECEIVED_DATE_COLUMN,
    INVENTORY_COLUMN,
)


class Store(Protocol):
    def exists(self) -> bool: ...
    def load(self) -> set[str]: ...
    def add(self, asins: Sequence[str]) -> None: ...


class Notifier(Protocol):
    def notify(self, products: list[LaunchReadyProduct], due_date: str) -> list[str]: ...


def run_launch_ready_notification(
    rows: Sequence[Mapping[str, Any]], *, notifier: Notifier, store: Store, today: str
) -> int:
    is_first_run = not store.exists()
    products = collect_launch_ready_products(rows, notified_asins=store.load())

    if is_first_run:
        # 既に販売中の新商品にまとめてタスクが立たないよう、初回は現状を記録するだけにする。
        store.add([p.asin for p in products])
        logger.info("初回実行のため %d件を通知済みとして記録しました（タスクは作りません）", len(products))
        return 0

    if not products:
        logger.info("販売開始待ちの新商品はありません")
        return 0

    notified = notifier.notify(products, today)
    if notified:
        store.add(notified)
    logger.info("✓ %d件の販売開始タスクを作成しました", len(notified))
    return len(notified)


def _read_rows(repo: BaseSheetsRepository, config: AppConfig) -> list[dict[str, Any]]:
    # 「状態」列は数式で他の列から導出されるため、抽出条件には使わない（循環する）。
    sheet = PurchaseSheet(repo, config.sheet_id, config.purchase_sheet_name)
    return [{column: row.get(column) for column in READ_COLUMNS} for row in sheet.data]


def list_launch_ready(
    config: AppConfig, repo: BaseSheetsRepository, *, store: Store | None = None
) -> list[LaunchReadyProduct]:
    store = store or NotifiedAsinStore(NOTIFIED_STORE_PATH)
    return collect_launch_ready_products(_read_rows(repo, config), notified_asins=store.load())


def notify_launch_ready(
    config: AppConfig,
    repo: BaseSheetsRepository,
    *,
    notifier: Notifier | None = None,
    store: Store | None = None,
    today: str | None = None,
) -> int:
    notifier = notifier or LaunchReadyNotifier(
        api_token=getattr(config, "todoist_api_token", ""),
        project=getattr(config, "todoist_project", "INBOX"),
    )
    store = store or NotifiedAsinStore(NOTIFIED_STORE_PATH)
    return run_launch_ready_notification(
        _read_rows(repo, config), notifier=notifier, store=store, today=today or date.today().isoformat()
    )
