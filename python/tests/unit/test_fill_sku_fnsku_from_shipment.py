from __future__ import annotations

from usecases import fill_sku_fnsku_from_shipment as mod


class FakeWorksheet:
    def __init__(self, values):
        self._values = values
        self.batched = []

    def get_all_values(self):
        return self._values

    def batch_update(self, data, value_input_option=None):
        self.batched.append((data, value_input_option))


class FakeRepo:
    def __init__(self, ws):
        self._ws = ws

    def open_worksheet(self, sheet_id, sheet_name):
        return self._ws


class FakeConfig:
    sheet_id = "SID"
    purchase_sheet_name = "仕入管理"
    api_key = "k"
    api_secret = "s"
    refresh_token = "r"


class FakeCreator:
    def __init__(self, items_by_shipment):
        self._items = items_by_shipment

    def get_shipment_items(self, shipment_id):
        return self._items.get(shipment_id, [])


def _sheet_values():
    # HEADER_ROW=4。ヘッダーに 状態/ASIN/SKU/FNSKU/納品プラン
    header = ["状態", "ASIN", "SKU", "FNSKU", "納品プラン"]
    return [
        ["", "", "", "", ""],
        ["", "", "", "", ""],
        ["", "", "", "", ""],
        header,
        ["発送済み", "B0FCHM6QQR", "DB-T0OT-ZDCG", "", "FBA15G8F5BCV"],  # 行5: FNSKU補完
        ["在庫あり", "B0X", "SKU-X", "FN-X", "FBA15GAAAAAA"],             # 行6: 対象外(状態)
        ["自宅発送", "B0Y", "", "", "FBA15GBBBBBB"],                     # 行7: 単一SKUで両方補完
    ]


def test_fills_missing_fnsku_and_both(monkeypatch):
    ws = FakeWorksheet(_sheet_values())
    repo = FakeRepo(ws)
    items = {
        "FBA15G8F5BCV": [{"SellerSKU": "DB-T0OT-ZDCG", "FulfillmentNetworkSKU": "X001APUHB1"}],
        "FBA15GBBBBBB": [{"SellerSKU": "YY-SKU", "FulfillmentNetworkSKU": "X009"}],
    }
    monkeypatch.setattr(mod, "get_auth_token", lambda *a, **k: "tok")
    monkeypatch.setattr(mod, "InboundPlanCreator", lambda tok: FakeCreator(items))

    mod.fill_sku_fnsku_from_shipment(FakeConfig(), repo)

    flat = []
    for data, _ in ws.batched:
        flat.extend(data)
    cells = {d["range"]: d["values"][0][0] for d in flat}
    # FNSKU列=D(4列目), SKU列=C(3列目)
    assert cells.get("D5") == "X001APUHB1"
    assert cells.get("C7") == "YY-SKU"
    assert cells.get("D7") == "X009"
    # 行6(在庫あり)は触らない
    assert "C6" not in cells and "D6" not in cells


def test_noop_when_nothing_to_fill(monkeypatch):
    header = ["状態", "ASIN", "SKU", "FNSKU", "納品プラン"]
    values = [["", "", "", "", ""]] * 3 + [header, ["発送済み", "B0Z", "SKU-Z", "FN-Z", "FBA15GCCCCCC"]]
    ws = FakeWorksheet(values)
    monkeypatch.setattr(mod, "get_auth_token", lambda *a, **k: "tok")
    monkeypatch.setattr(mod, "InboundPlanCreator", lambda tok: FakeCreator({}))
    mod.fill_sku_fnsku_from_shipment(FakeConfig(), FakeRepo(ws))
    assert ws.batched == []
