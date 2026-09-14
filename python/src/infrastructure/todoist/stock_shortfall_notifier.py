from __future__ import annotations

import logging
from typing import Any, Protocol

import requests

from domain.inventory.value_objects.stock_shortfall import StockShortfall

logger = logging.getLogger(__name__)

# v2 は 2026-04 に廃止され 410 を返す。他リポジトリにも同じクライアントがあるので、
# ここを変えるときは tests/infrastructure/test_stock_shortfall_notifier.py も見ること。
TASKS_ENDPOINT = "https://api.todoist.com/api/v1/tasks"
TASK_PREFIX = "FBA在庫が仕入管理の行に収まっていない"
TIMEOUT_SECONDS = 15


class HttpSession(Protocol):
    def post(self, url: str, headers: dict, json: dict, timeout: int) -> Any: ...


class StockShortfallNotifier:
    def __init__(
        self, api_token: str, project: str = "INBOX", session: HttpSession | None = None
    ) -> None:
        self._api_token = api_token
        self._project = project
        self._session = session or requests.Session()

    def notify(self, shortfalls: list[StockShortfall], due_date: str) -> None:
        if not shortfalls:
            return
        if not self._api_token:
            logger.warning(
                "TODOIST_API_TOKEN が未設定のため通知しません: %d件 %d個",
                len(shortfalls),
                sum(s.quantity for s in shortfalls),
            )
            return
        payload: dict[str, Any] = {
            "content": task_content(shortfalls),
            "description": task_description(shortfalls),
            "due_date": due_date,
        }
        if self._project and self._project.upper() != "INBOX":
            payload["project_id"] = self._project
        response = self._session.post(
            TASKS_ENDPOINT,
            headers={
                "Authorization": f"Bearer {self._api_token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=TIMEOUT_SECONDS,
        )
        if response.status_code >= 400:
            raise RuntimeError(
                f"Todoist API エラー HTTP {response.status_code}: {response.text[:200]}"
            )
        logger.info("Todoist へ登録しました: %s", payload["content"])


def task_content(shortfalls: list[StockShortfall]) -> str:
    total = sum(s.quantity for s in shortfalls)
    return f"{TASK_PREFIX} {len(shortfalls)}件 {total:,}個"


def task_description(shortfalls: list[StockShortfall]) -> str:
    lines = [
        "FBAにある在庫が仕入管理のロット行に割り当てきれていません。",
        "受け皿の行が消えたか、まだ登録されていない可能性があります。",
        "（受領中の行は購入数を受け皿として数えているので、部分受領は出ません）",
        "",
    ]
    lines += [
        f"- {s.product_url} 実FBA {s.fba_quantity:,} / 受け皿 {s.capacity_quantity:,} "
        f"→ 未割当 {s.quantity:,}"
        for s in shortfalls
    ]
    return "\n".join(lines)
