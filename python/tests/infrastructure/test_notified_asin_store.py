from __future__ import annotations

from infrastructure.store.notified_asin_store import NotifiedAsinStore


def test_missing_file_is_reported_as_not_existing(tmp_path):
    store = NotifiedAsinStore(tmp_path / "notified.json")

    assert store.exists() is False
    assert store.load() == set()


def test_added_asins_are_persisted(tmp_path):
    path = tmp_path / "notified.json"
    NotifiedAsinStore(path).add(["A1", "A2"])

    assert NotifiedAsinStore(path).load() == {"A1", "A2"}
    assert NotifiedAsinStore(path).exists() is True


def test_adding_keeps_previously_stored_asins(tmp_path):
    path = tmp_path / "notified.json"
    NotifiedAsinStore(path).add(["A1"])
    NotifiedAsinStore(path).add(["A2"])

    assert NotifiedAsinStore(path).load() == {"A1", "A2"}


def test_adding_nothing_still_creates_the_file(tmp_path):
    """初回実行を1度きりにするため、0件でもファイルを作る"""
    path = tmp_path / "notified.json"
    NotifiedAsinStore(path).add([])

    assert NotifiedAsinStore(path).exists() is True


def test_broken_file_is_treated_as_empty(tmp_path):
    path = tmp_path / "notified.json"
    path.write_text("{壊れている", encoding="utf-8")

    assert NotifiedAsinStore(path).load() == set()
