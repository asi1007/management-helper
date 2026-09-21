from domain.inventory.value_objects.launch_ready_product import (
    LaunchReadyProduct,
    collect_launch_ready_products,
)


def _row(**overrides):
    row = {"ASIN": "A1", "商品名": "新商品", "仕入回数": 1, "受領日": "2026-09-14", "在庫数": 300}
    row.update(overrides)
    return row


def test_first_purchase_with_received_date_is_launch_ready():
    products = collect_launch_ready_products([_row()], notified_asins=set())

    assert products == [
        LaunchReadyProduct(asin="A1", product_name="新商品", received_date="2026-09-14", inventory_quantity=300)
    ]


def test_repeat_purchase_is_not_launch_ready():
    assert collect_launch_ready_products([_row(仕入回数=2)], notified_asins=set()) == []


def test_row_without_received_date_is_not_launch_ready():
    assert collect_launch_ready_products([_row(受領日="")], notified_asins=set()) == []


def test_row_without_purchase_count_is_not_launch_ready():
    """仕入回数が空の行は新商品か判断できないので対象にしない"""
    assert collect_launch_ready_products([_row(仕入回数="")], notified_asins=set()) == []


def test_already_notified_asin_is_skipped():
    assert collect_launch_ready_products([_row()], notified_asins={"A1"}) == []


def test_same_asin_appears_only_once():
    rows = [_row(), _row(在庫数=10)]

    products = collect_launch_ready_products(rows, notified_asins=set())

    assert [p.asin for p in products] == ["A1"]


def test_row_without_asin_is_skipped():
    assert collect_launch_ready_products([_row(ASIN="")], notified_asins=set()) == []


def test_blank_inventory_is_treated_as_zero():
    products = collect_launch_ready_products([_row(在庫数="")], notified_asins=set())

    assert products[0].inventory_quantity == 0


def test_product_url_is_built_from_asin():
    product = LaunchReadyProduct(asin="A1", product_name="x", received_date="2026-09-14", inventory_quantity=1)

    assert product.product_url == "https://www.amazon.co.jp/dp/A1"
