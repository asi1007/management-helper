from __future__ import annotations

from infrastructure.amazon.inbound_plan_creator import InboundPlanCreator


def _creator_with_pages(pages):
    creator = InboundPlanCreator("dummy-token")
    calls = {"i": 0}

    def fake_fetch(shipment_id, next_token):
        i = calls["i"]
        calls["i"] += 1
        return pages[i]

    creator._fetch_items_page = fake_fetch
    return creator


def test_aggregates_multiple_pages_dedup_by_sku():
    pages = [
        ([{"SellerSKU": "A", "QuantityReceived": 5}], "t1"),
        ([{"SellerSKU": "B", "QuantityReceived": 3}], "t2"),
        ([{"SellerSKU": "A", "QuantityReceived": 5}], "t1"),
    ]
    creator = _creator_with_pages(pages)
    items = creator.get_shipment_items("FBAXXXXXXXXX")
    skus = sorted(i["SellerSKU"] for i in items)
    assert skus == ["A", "B"]


def test_looping_same_page_does_not_infinite_loop():
    same = ([{"SellerSKU": "A", "QuantityReceived": 41},
             {"SellerSKU": "B", "QuantityReceived": 6}], "loop-token")
    creator = _creator_with_pages([same] * 100)
    items = creator.get_shipment_items("FBAXXXXXXXXX")
    assert sorted(i["SellerSKU"] for i in items) == ["A", "B"]


def test_single_page_no_token():
    creator = _creator_with_pages([([{"SellerSKU": "A", "QuantityReceived": 1}], None)])
    items = creator.get_shipment_items("FBAXXXXXXXXX")
    assert [i["SellerSKU"] for i in items] == ["A"]
