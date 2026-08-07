from __future__ import annotations

from usecases.set_packing_info import (
    build_packing_body,
    extract_inbound_plan_id,
    parse_carton_input,
)

FULL_PLAN_ID = "wfe6a9d3d4-3de1-4808-9e7e-d27f55e68e02"


class TestExtractInboundPlanId:
    def test_ハイフン付きの完全なプランIDを取り出す(self) -> None:
        assert extract_inbound_plan_id(FULL_PLAN_ID) == FULL_PLAN_ID

    def test_URLのwfパラメータから取り出す(self) -> None:
        cell = f"https://sellercentral.amazon.co.jp/fba/sendtoamazon/confirm_content_step?wf={FULL_PLAN_ID}"
        assert extract_inbound_plan_id(cell) == FULL_PLAN_ID

    def test_batch_labelsが書く短縮表示にも対応する(self) -> None:
        assert extract_inbound_plan_id("wfe5c091ef") == "wfe5c091ef"

    def test_プランIDがなければ空文字(self) -> None:
        assert extract_inbound_plan_id("") == ""


class TestBuildPackingBody:
    def test_箱ごとにlabelOwnerとprepOwnerとcontentInformationSourceを含める(self) -> None:
        cartons = parse_carton_input("1：50*40*23 18KG")
        items = [{"msku": "2K-480G-SL04", "quantity": 503, "labelOwner": "SELLER"}]
        body = build_packing_body("pg-1", cartons, items)

        box = body["packageGroupings"][0]["boxes"][0]
        assert box["contentInformationSource"] == "BOX_CONTENT_PROVIDED"
        assert box["items"] == [
            {"msku": "2K-480G-SL04", "quantity": 503, "labelOwner": "SELLER", "prepOwner": "NONE"},
        ]

    def test_センチとキロのままAPIへ送る(self) -> None:
        cartons = parse_carton_input("1：50*40*23 18KG")
        body = build_packing_body("pg-1", cartons, [{"msku": "SKU-1", "quantity": 1}])

        box = body["packageGroupings"][0]["boxes"][0]
        assert box["dimensions"] == {
            "unitOfMeasurement": "CM", "length": 50.0, "width": 40.0, "height": 23.0,
        }
        assert box["weight"] == {"unit": "KG", "value": 18.0}

    def test_ラベル貼付のprepはprepOwnerに含めない(self) -> None:
        cartons = parse_carton_input("1：50*40*23 18KG")
        items = [{
            "msku": "SKU-1", "quantity": 1, "labelOwner": "SELLER",
            "prepInstructions": [{"prepType": "ITEM_LABELING", "prepOwner": "SELLER"}],
        }]
        body = build_packing_body("pg-1", cartons, items)

        assert body["packageGroupings"][0]["boxes"][0]["items"][0]["prepOwner"] == "NONE"

    def test_ラベル貼付以外のprepはprepOwnerに反映する(self) -> None:
        cartons = parse_carton_input("1：50*40*23 18KG")
        items = [{
            "msku": "SKU-1", "quantity": 1, "labelOwner": "SELLER",
            "prepInstructions": [
                {"prepType": "ITEM_LABELING", "prepOwner": "SELLER"},
                {"prepType": "ITEM_POLYBAGGING", "prepOwner": "AMAZON"},
            ],
        }]
        body = build_packing_body("pg-1", cartons, items)

        assert body["packageGroupings"][0]["boxes"][0]["items"][0]["prepOwner"] == "AMAZON"

    def test_複数箱の範囲指定を箱数に展開する(self) -> None:
        cartons = parse_carton_input("1-3：60*40*32 29.1KG")
        body = build_packing_body("pg-1", cartons, [{"msku": "SKU-1", "quantity": 30}])

        assert body["packageGroupings"][0]["boxes"][0]["quantity"] == 3
