from __future__ import annotations

from usecases import update_status_estimate as mod


class FakeConfig:
    api_key = "k"
    api_secret = "s"
    refresh_token = "r"
    sheet_id = "SID"
    purchase_sheet_name = "仕入管理"


def test_update_status_calls_fill_first(monkeypatch):
    calls = []
    monkeypatch.setattr(mod, "get_auth_token", lambda *a, **k: "tok")
    monkeypatch.setattr(mod, "InboundPlanCreator", lambda tok: object())
    monkeypatch.setattr(mod, "fill_sku_fnsku_from_shipment", lambda config, repo: calls.append("fill"))

    class FakeSheet:
        data = []
        def __init__(self, *a, **k): pass
        def filter(self, *a, **k): calls.append("filter")

    monkeypatch.setattr(mod, "PurchaseSheet", FakeSheet)

    mod.update_status_estimate(config=FakeConfig(), repo=object())
    assert calls and calls[0] == "fill"  # 補完が最初に走る
