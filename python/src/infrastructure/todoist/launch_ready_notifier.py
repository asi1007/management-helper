from __future__ import annotations

import logging
from typing import Any, Protocol

import requests

from domain.inventory.value_objects.launch_ready_product import LaunchReadyProduct

logger = logging.getLogger(__name__)

# v2 は 2026-04 に廃止され 410 を返す。stock_shortfall_notifier.py にも同じ定数がある。
TASKS_ENDPOINT = "https://api.todoist.com/api/v1/tasks"
TIMEOUT_SECONDS = 15
MAX_NAME_LENGTH = 40


class HttpSession(Protocol):
    def post(self, url: str, headers: dict, json: dict, timeout: int) -> Any: ...


def task_content(product: LaunchReadyProduct) -> str:
    name = product.product_name or product.asin
    if len(name) > MAX_NAME_LENGTH:
        name = name[:MAX_NAME_LENGTH] + "…"
    return f"{name} を販売開始にする"


def _date_only(received_date: str) -> str:
    # シートの受領日は「2026/02/13 16:30:46」で入っている行がある
    return str(received_date or "").split(" ")[0]


def task_description(product: LaunchReadyProduct) -> str:
    return "\n".join([
        "初回仕入の在庫が受領されました。販売開始の作業をしてください。",
        "",
        "- 広告を出稿する",
        "- Vine に登録する",
        "",
        product.product_url,
        f"受領日 {_date_only(product.received_date)} / 在庫数 {product.inventory_quantity:,}",
    ])


class LaunchReadyNotifier:
    def __init__(
        self, api_token: str, project: str = "INBOX", session: HttpSession | None = None
    ) -> None:
        self._api_token = api_token
        self._project = project
        self._session = session or requests.Session()

    def notify(self, products: list[LaunchReadyProduct], due_date: str) -> list[str]:
        if not products:
            return []
        if not self._api_token:
            logger.warning(
                "TODOIST_API_TOKEN が未設定のため通知しません: %s",
                ", ".join(p.asin for p in products),
            )
            return []

        notified: list[str] = []
        for product in products:
            self._create_task(product, due_date)
            notified.append(product.asin)
        return notified

    def _create_task(self, product: LaunchReadyProduct, due_date: str) -> None:
        payload: dict[str, Any] = {
            "content": task_content(product),
            "description": task_description(product),
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
