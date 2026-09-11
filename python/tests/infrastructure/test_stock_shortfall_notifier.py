from __future__ import annotations

import pytest

from domain.inventory.value_objects.stock_shortfall import StockShortfall
from infrastructure.todoist.stock_shortfall_notifier import (
    TASKS_ENDPOINT,
    StockShortfallNotifier,
)

SHORTFALLS = [
    StockShortfall(asin="B0DHTN6C5P", fba_quantity=2156, assigned_quantity=0),
    StockShortfall(asin="B0FN4L3TJC", fba_quantity=4713, assigned_quantity=4000),
]


class FakeResponse:
    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code
        self.text = ""

    def json(self) -> dict:
        return {"id": "1"}


class FakeSession:
    def __init__(self, status_code: int = 200) -> None:
        self.calls: list[dict] = []
        self._status_code = status_code

    def post(self, url, headers=None, json=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "json": json})
        return FakeResponse(self._status_code)


def test_uses_the_v1_endpoint() -> None:
    # v2 は 2026-04 に廃止され 410 を返す。ここを変えるとタスクが作られないまま成功に見える
    assert TASKS_ENDPOINT == "https://api.todoist.com/api/v1/tasks"


def test_creates_one_task_listing_every_shortfall() -> None:
    session = FakeSession()
    StockShortfallNotifier(api_token="t", session=session).notify(SHORTFALLS, "2026-09-11")

    assert len(session.calls) == 1
    payload = session.calls[0]["json"]
    assert "2件" in payload["content"]
    assert "B0DHTN6C5P" in payload["description"]
    assert "https://www.amazon.co.jp/dp/B0FN4L3TJC" in payload["description"]
    assert payload["due_date"] == "2026-09-11"


def test_sends_the_bearer_token() -> None:
    session = FakeSession()
    StockShortfallNotifier(api_token="secret", session=session).notify(SHORTFALLS, "2026-09-11")

    assert session.calls[0]["headers"]["Authorization"] == "Bearer secret"


def test_omits_project_id_for_the_inbox() -> None:
    session = FakeSession()
    StockShortfallNotifier(api_token="t", project="INBOX", session=session).notify(
        SHORTFALLS, "2026-09-11"
    )

    assert "project_id" not in session.calls[0]["json"]


def test_does_nothing_without_shortfalls() -> None:
    session = FakeSession()
    StockShortfallNotifier(api_token="t", session=session).notify([], "2026-09-11")

    assert session.calls == []


def test_does_nothing_without_a_token() -> None:
    session = FakeSession()
    StockShortfallNotifier(api_token="", session=session).notify(SHORTFALLS, "2026-09-11")

    assert session.calls == []


def test_raises_when_todoist_rejects_the_task() -> None:
    session = FakeSession(status_code=400)

    with pytest.raises(RuntimeError):
        StockShortfallNotifier(api_token="t", session=session).notify(SHORTFALLS, "2026-09-11")
