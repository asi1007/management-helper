"""納品分類の自動判定ユースケースのテスト"""
from __future__ import annotations

import pytest

from domain.shipment.delivery_category import DeliveryCategoryUndecidable
from usecases.classify_delivery_category import classify_delivery_category

TARGET_ASIN = "B0NEW00001"
TARGET_SKU = "SKU-NEW"


@pytest.fixture(autouse=True)
def reference_skus(mocker):
    """代表SKUは shared/config.py の定数から取る（実績で裏の取れたSKUのみ）"""
    references = {"ノーマル": ["SKU-REF-N"], "ファッション": ["SKU-REF-F"]}
    mocker.patch.dict(
        "usecases.classify_delivery_category.DELIVERY_CATEGORY_REFERENCE_SKUS",
        references,
        clear=True,
    )
    return references


def _sales_mock(
    mocker,
    *,
    categories: dict[str, str] | None = None,
    sku_by_asin: dict[str, dict[str, str]] | None = None,
):
    sales = mocker.Mock()
    sales.load_delivery_category_by_asin.return_value = categories or {}
    sales.load_asin_to_sku_fnsku.return_value = sku_by_asin if sku_by_asin is not None else {
        TARGET_ASIN: {"sku": TARGET_SKU, "fnsku": "X001NEW"}
    }
    sales.write_delivery_category.return_value = [10]
    return sales


def _creator_mock(mocker, packing_groups: list[list[str]]):
    creator = mocker.Mock()
    creator.create_plan.return_value = {"inboundPlanId": "wf-trial", "link": "https://example/wf-trial"}
    creator.get_packing_groups.return_value = [
        {"packingGroupId": f"pg-{i}", "items": [{"msku": sku} for sku in group]}
        for i, group in enumerate(packing_groups)
    ]
    return creator


def test_ノーマル代表と同居すればノーマルを書き込む(mocker):
    sales = _sales_mock(mocker)
    creator = _creator_mock(mocker, [[TARGET_SKU, "SKU-REF-N"], ["SKU-REF-F"]])

    result = classify_delivery_category(TARGET_ASIN, sales=sales, creator=creator)

    assert result.category == "ノーマル"
    assert result.inbound_plan_id == "wf-trial"
    sales.write_delivery_category.assert_called_once_with(TARGET_ASIN, "ノーマル")


def test_試作プランは判定後にキャンセルされる(mocker):
    sales = _sales_mock(mocker)
    creator = _creator_mock(mocker, [[TARGET_SKU, "SKU-REF-F"], ["SKU-REF-N"]])

    result = classify_delivery_category(TARGET_ASIN, sales=sales, creator=creator)

    assert result.category == "ファッション"
    creator.cancel_inbound_plan.assert_called_once_with("wf-trial")


def test_試作プランは判定不能でもキャンセルされる(mocker):
    sales = _sales_mock(mocker)
    creator = _creator_mock(mocker, [[TARGET_SKU], ["SKU-REF-N"], ["SKU-REF-F"]])

    with pytest.raises(DeliveryCategoryUndecidable):
        classify_delivery_category(TARGET_ASIN, sales=sales, creator=creator)

    creator.cancel_inbound_plan.assert_called_once_with("wf-trial")
    sales.write_delivery_category.assert_not_called()


def test_キャンセルに失敗しても判定結果は返る(mocker):
    sales = _sales_mock(mocker)
    creator = _creator_mock(mocker, [[TARGET_SKU, "SKU-REF-N"], ["SKU-REF-F"]])
    creator.cancel_inbound_plan.side_effect = RuntimeError("cancel failed")

    result = classify_delivery_category(TARGET_ASIN, sales=sales, creator=creator)

    assert result.category == "ノーマル"
    assert result.cancel_failed is True


def test_既に分類済みならプランを作らずスキップする(mocker):
    sales = _sales_mock(mocker, categories={TARGET_ASIN: "ファッション"})
    creator = _creator_mock(mocker, [])

    result = classify_delivery_category(TARGET_ASIN, sales=sales, creator=creator)

    assert result.category == "ファッション"
    assert result.skipped is True
    creator.create_plan.assert_not_called()
    sales.write_delivery_category.assert_not_called()


def test_overwriteなら分類済みでも再判定する(mocker):
    sales = _sales_mock(mocker, categories={TARGET_ASIN: "ファッション"})
    creator = _creator_mock(mocker, [[TARGET_SKU, "SKU-REF-N"], ["SKU-REF-F"]])

    result = classify_delivery_category(TARGET_ASIN, sales=sales, creator=creator, overwrite=True)

    assert result.category == "ノーマル"
    assert result.skipped is False
    sales.write_delivery_category.assert_called_once_with(TARGET_ASIN, "ノーマル")


def test_dry_runなら書き込まない(mocker):
    sales = _sales_mock(mocker)
    creator = _creator_mock(mocker, [[TARGET_SKU, "SKU-REF-N"], ["SKU-REF-F"]])

    result = classify_delivery_category(TARGET_ASIN, sales=sales, creator=creator, dry_run=True)

    assert result.category == "ノーマル"
    sales.write_delivery_category.assert_not_called()
    creator.cancel_inbound_plan.assert_called_once_with("wf-trial")


def test_売上日にSKUが無ければresolve_skuで解決する(mocker):
    sales = _sales_mock(mocker, sku_by_asin={})
    creator = _creator_mock(mocker, [[TARGET_SKU, "SKU-REF-N"], ["SKU-REF-F"]])
    resolve_sku = mocker.Mock(return_value=TARGET_SKU)

    result = classify_delivery_category(
        TARGET_ASIN, sales=sales, creator=creator, resolve_sku=resolve_sku
    )

    assert result.category == "ノーマル"
    resolve_sku.assert_called_once_with(TARGET_ASIN)


def test_SKUが解決できなければエラー(mocker):
    sales = _sales_mock(mocker, sku_by_asin={})
    creator = _creator_mock(mocker, [])

    with pytest.raises(RuntimeError, match="SKU"):
        classify_delivery_category(TARGET_ASIN, sales=sales, creator=creator)

    creator.create_plan.assert_not_called()


def test_代表SKUが欠けていればエラー(mocker):
    mocker.patch.dict(
        "usecases.classify_delivery_category.DELIVERY_CATEGORY_REFERENCE_SKUS",
        {"ノーマル": ["SKU-REF-N"], "ファッション": []},
        clear=True,
    )
    sales = _sales_mock(mocker)
    creator = _creator_mock(mocker, [])

    with pytest.raises(RuntimeError, match="ファッション"):
        classify_delivery_category(TARGET_ASIN, sales=sales, creator=creator)

    creator.create_plan.assert_not_called()


def test_対象SKU自身は代表候補から除かれる(mocker):
    """判定したい商品が代表SKUとして登録済みでも、同じSKUを二重に投入しない"""
    mocker.patch.dict(
        "usecases.classify_delivery_category.DELIVERY_CATEGORY_REFERENCE_SKUS",
        {"ノーマル": [TARGET_SKU, "SKU-REF-N"], "ファッション": ["SKU-REF-F"]},
        clear=True,
    )
    sales = _sales_mock(mocker)
    creator = _creator_mock(mocker, [[TARGET_SKU, "SKU-REF-N"], ["SKU-REF-F"]])

    result = classify_delivery_category(TARGET_ASIN, sales=sales, creator=creator)

    assert result.category == "ノーマル"
    items = creator.create_plan.call_args.args[0]
    assert set(items) == {TARGET_SKU, "SKU-REF-N", "SKU-REF-F"}


def test_プラン作成に失敗したら次の代表候補で再試行する(mocker):
    mocker.patch.dict(
        "usecases.classify_delivery_category.DELIVERY_CATEGORY_REFERENCE_SKUS",
        {"ノーマル": ["SKU-REF-N1", "SKU-REF-N2"], "ファッション": ["SKU-REF-F1", "SKU-REF-F2"]},
        clear=True,
    )
    sales = _sales_mock(mocker)
    creator = _creator_mock(mocker, [[TARGET_SKU, "SKU-REF-N2"], ["SKU-REF-F2"]])
    creator.create_plan.side_effect = [
        RuntimeError("納品プラン作成エラー: SKU-REF-N1 は無効"),
        {"inboundPlanId": "wf-trial", "link": "https://example/wf-trial"},
    ]

    result = classify_delivery_category(TARGET_ASIN, sales=sales, creator=creator)

    assert result.category == "ノーマル"
    assert creator.create_plan.call_count == 2
    second_items = creator.create_plan.call_args_list[1].args[0]
    assert set(second_items) == {TARGET_SKU, "SKU-REF-N2", "SKU-REF-F2"}


def test_全候補で失敗したら試行内容を含むエラー(mocker):
    sales = _sales_mock(mocker)
    creator = _creator_mock(mocker, [])
    creator.create_plan.side_effect = RuntimeError("納品プラン作成エラー: 無効なSKU")

    with pytest.raises(RuntimeError, match="試作プラン"):
        classify_delivery_category(TARGET_ASIN, sales=sales, creator=creator)


def test_試作プランは対象と代表2件の3品で作られる(mocker):
    sales = _sales_mock(mocker)
    creator = _creator_mock(mocker, [[TARGET_SKU, "SKU-REF-N"], ["SKU-REF-F"]])

    classify_delivery_category(TARGET_ASIN, sales=sales, creator=creator)

    items = creator.create_plan.call_args.args[0]
    assert set(items) == {TARGET_SKU, "SKU-REF-N", "SKU-REF-F"}
    assert items[TARGET_SKU] == {
        "msku": TARGET_SKU, "asin": TARGET_ASIN, "quantity": 1, "labelOwner": "SELLER",
    }
    assert items["SKU-REF-N"]["quantity"] == 1


def test_売上日のSKUが数式エラーならresolve_skuで解決する(mocker):
    sales = _sales_mock(mocker, sku_by_asin={TARGET_ASIN: {"sku": "#N/A", "fnsku": ""}})
    creator = _creator_mock(mocker, [[TARGET_SKU, "SKU-REF-N"], ["SKU-REF-F"]])
    resolve_sku = mocker.Mock(return_value=TARGET_SKU)

    result = classify_delivery_category(
        TARGET_ASIN, sales=sales, creator=creator, resolve_sku=resolve_sku
    )

    assert result.category == "ノーマル"
    resolve_sku.assert_called_once_with(TARGET_ASIN)


def test_売上日のSKUが数式エラーならresolve_skuで解決する(mocker):
    sales = _sales_mock(mocker, sku_by_asin={TARGET_ASIN: {"sku": "#N/A", "fnsku": ""}})
    creator = _creator_mock(mocker, [[TARGET_SKU, "SKU-REF-N"], ["SKU-REF-F"]])
    resolve_sku = mocker.Mock(return_value=TARGET_SKU)

    classify_delivery_category(TARGET_ASIN, sales=sales, creator=creator, resolve_sku=resolve_sku)

    resolve_sku.assert_called_once_with(TARGET_ASIN)


def test_売上日のSKUがSKUハイフン数字でもそのまま使う(mocker):
    # create_listing.py が付ける本番SKU。形式で仮SKU扱いして弾いていた
    sales = _sales_mock(
        mocker, sku_by_asin={TARGET_ASIN: {"sku": "SKU-20260830090814", "fnsku": ""}}
    )
    creator = _creator_mock(mocker, [["SKU-20260830090814", "SKU-REF-N"], ["SKU-REF-F"]])
    resolve_sku = mocker.Mock()

    classify_delivery_category(TARGET_ASIN, sales=sales, creator=creator, resolve_sku=resolve_sku)

    resolve_sku.assert_not_called()


def test_resolve_skuが空を返したらエラー(mocker):
    sales = _sales_mock(mocker, sku_by_asin={})
    creator = _creator_mock(mocker, [])
    resolve_sku = mocker.Mock(return_value="")

    with pytest.raises(RuntimeError, match="SKU"):
        classify_delivery_category(
            TARGET_ASIN, sales=sales, creator=creator, resolve_sku=resolve_sku
        )
    creator.create_plan.assert_not_called()
