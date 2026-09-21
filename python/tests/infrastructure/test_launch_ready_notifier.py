from __future__ import annotations

from domain.inventory.value_objects.launch_ready_product import LaunchReadyProduct
from infrastructure.todoist.launch_ready_notifier import (
    TASKS_ENDPOINT,
    LaunchReadyNotifier,
    task_content,
)

PRODUCTS = [
    LaunchReadyProduct(
        asin="B0F84WCNWH",
        product_name="ｂｅｎｒｉｉ チェストストラップ ブラック 調整可能リュックずれ落ち防止ストラップ バックル式 バックパック",
        received_date="2026-09-14",
        inventory_quantity=300,
    ),
    LaunchReadyProduct(asin="B0G1J3NW6Y", product_name="ルーペ", received_date="2026-09-13", inventory_quantity=0),
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
    assert TASKS_ENDPOINT == "https://api.todoist.com/api/v1/tasks"


def test_creates_one_task_per_product() -> None:
    session = FakeSession()

    notified = LaunchReadyNotifier(api_token="t", session=session).notify(PRODUCTS, "2026-09-14")

    assert len(session.calls) == 2
    assert notified == ["B0F84WCNWH", "B0G1J3NW6Y"]


def test_task_names_the_product_and_the_action() -> None:
    session = FakeSession()
    LaunchReadyNotifier(api_token="t", session=session).notify(PRODUCTS[:1], "2026-09-14")

    payload = session.calls[0]["json"]
    assert payload["content"].endswith("を販売開始にする")
    assert "ｂｅｎｒｉｉ チェストストラップ" in payload["content"]
    assert payload["due_date"] == "2026-09-14"


def test_long_product_name_is_trimmed_in_the_task_name() -> None:
    long_name = "あ" * 80
    trimmed = task_content(
        LaunchReadyProduct(asin="A1", product_name=long_name, received_date="2026-09-14", inventory_quantity=1)
    )

    assert len(trimmed) < len(long_name)
    assert "…" in trimmed


def test_description_carries_the_link_and_what_to_do() -> None:
    session = FakeSession()
    LaunchReadyNotifier(api_token="t", session=session).notify(PRODUCTS[:1], "2026-09-14")

    description = session.calls[0]["json"]["description"]
    assert "https://www.amazon.co.jp/dp/B0F84WCNWH" in description
    assert "広告を出稿する" in description
    assert "Vine に登録する" in description
    assert "2026-09-14" in description
    assert "300" in description


def test_nothing_is_sent_without_a_token() -> None:
    session = FakeSession()

    notified = LaunchReadyNotifier(api_token="", session=session).notify(PRODUCTS, "2026-09-14")

    assert session.calls == []
    # 送れていないので通知済みにしない（トークンを直したあとに拾えるようにする）
    assert notified == []


def test_api_error_stops_the_run() -> None:
    session = FakeSession(status_code=500)

    try:
        LaunchReadyNotifier(api_token="t", session=session).notify(PRODUCTS[:1], "2026-09-14")
    except RuntimeError as e:
        assert "500" in str(e)
    else:
        raise AssertionError("RuntimeError が送出されること")


def test_received_date_drops_the_time_part() -> None:
    """シートの受領日は「2026/02/13 16:30:46」の形で入っている行がある"""
    session = FakeSession()
    product = LaunchReadyProduct(
        asin="A1", product_name="x", received_date="2026/02/13 16:30:46", inventory_quantity=1
    )

    LaunchReadyNotifier(api_token="t", session=session).notify([product], "2026-09-14")

    assert "受領日 2026/02/13 /" in session.calls[0]["json"]["description"]
