from __future__ import annotations

from usecases.notify_launch_ready import run_launch_ready_notification


class FakeStore:
    def __init__(self, asins: set[str] | None = None, exists: bool = True) -> None:
        self._asins = set(asins or set())
        self._exists = exists
        self.added: list[list[str]] = []

    def exists(self) -> bool:
        return self._exists

    def load(self) -> set[str]:
        return set(self._asins)

    def add(self, asins) -> None:
        added = list(asins)
        self.added.append(added)
        self._asins |= set(added)
        self._exists = True


class FakeNotifier:
    def __init__(self, notified: list[str] | None = None) -> None:
        self.calls: list[list] = []
        self._notified = notified

    def notify(self, products, due_date) -> list[str]:
        self.calls.append(products)
        if self._notified is not None:
            return list(self._notified)
        return [p.asin for p in products]


def _row(asin: str, **overrides):
    row = {"ASIN": asin, "商品名": f"商品{asin}", "仕入回数": 1, "受領日": "2026-09-14", "在庫数": 10}
    row.update(overrides)
    return row


def test_first_run_records_existing_products_without_creating_tasks():
    """既に販売中の新商品にまとめてタスクが立つのを防ぐ"""
    store = FakeStore(exists=False)
    notifier = FakeNotifier()

    created = run_launch_ready_notification(
        [_row("A1"), _row("A2")], notifier=notifier, store=store, today="2026-09-14"
    )

    assert created == 0
    assert notifier.calls == []
    assert sorted(store.added[0]) == ["A1", "A2"]


def test_newly_received_product_creates_a_task():
    store = FakeStore({"A1"})
    notifier = FakeNotifier()

    created = run_launch_ready_notification(
        [_row("A1"), _row("A2")], notifier=notifier, store=store, today="2026-09-14"
    )

    assert created == 1
    assert [p.asin for p in notifier.calls[0]] == ["A2"]
    assert store.added == [["A2"]]


def test_nothing_happens_when_no_product_became_ready():
    store = FakeStore({"A1"})
    notifier = FakeNotifier()

    created = run_launch_ready_notification(
        [_row("A1")], notifier=notifier, store=store, today="2026-09-14"
    )

    assert created == 0
    assert notifier.calls == []
    assert store.added == []


def test_products_that_failed_to_notify_are_not_recorded():
    """トークン未設定などで送れなかった分は、直したあとに拾い直せるようにする"""
    store = FakeStore({"A1"})
    notifier = FakeNotifier(notified=[])

    created = run_launch_ready_notification(
        [_row("A2")], notifier=notifier, store=store, today="2026-09-14"
    )

    assert created == 0
    assert store.added == []
