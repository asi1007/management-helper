from infrastructure.amazon.inbound_plan_creator import InboundPlanCreator


def test_get_shipment_status_uses_getshipments_endpoint(mocker):
    creator = InboundPlanCreator("token")
    mock_resp = mocker.Mock()
    mock_resp.json.return_value = {
        "payload": {"ShipmentData": [{"ShipmentId": "FBA15G7TJQNF", "ShipmentStatus": "CLOSED"}]}
    }
    mock_get = mocker.patch(
        "infrastructure.amazon.inbound_plan_creator.httpx.get", return_value=mock_resp
    )

    status = creator.get_shipment_status("FBA15G7TJQNF")

    assert status == "CLOSED"
    called_url = mock_get.call_args[0][0]
    called_params = mock_get.call_args[1]["params"]
    assert called_url.endswith("/shipments")
    assert called_params["ShipmentIdList"] == "FBA15G7TJQNF"


def test_get_shipment_status_empty_when_no_data(mocker):
    creator = InboundPlanCreator("token")
    mock_resp = mocker.Mock()
    mock_resp.json.return_value = {"payload": {"ShipmentData": []}}
    mocker.patch(
        "infrastructure.amazon.inbound_plan_creator.httpx.get", return_value=mock_resp
    )

    assert creator.get_shipment_status("FBA000000000") == ""


def _mock_json_response(mocker, payload):
    resp = mocker.Mock()
    resp.json.return_value = payload
    resp.raise_for_status = mocker.Mock()
    return resp


def test_get_packing_groups_uses_packing_options_endpoint(mocker):
    creator = InboundPlanCreator("token")
    responses = [
        _mock_json_response(mocker, {"packingOptions": [{"packingGroups": ["pg-aaa", "pg-bbb"]}]}),
        _mock_json_response(mocker, {"items": [{"msku": "SKU-A"}]}),
        _mock_json_response(mocker, {"items": [{"msku": "SKU-B"}]}),
    ]
    mock_get = mocker.patch(
        "infrastructure.amazon.inbound_plan_creator.httpx.get", side_effect=responses
    )

    groups = creator.get_packing_groups("wf123")

    assert [g["packingGroupId"] for g in groups] == ["pg-aaa", "pg-bbb"]
    assert groups[0]["items"] == [{"msku": "SKU-A"}]
    urls = [call[0][0] for call in mock_get.call_args_list]
    # トップレベルの /packingGroups は権限外(403)のため packingOptions 経由で ID を取る
    assert urls[0].endswith("/inboundPlans/wf123/packingOptions")
    assert urls[1].endswith("/inboundPlans/wf123/packingGroups/pg-aaa/items")


def test_get_packing_groups_empty_when_no_packing_options(mocker):
    creator = InboundPlanCreator("token")
    mocker.patch(
        "infrastructure.amazon.inbound_plan_creator.httpx.get",
        return_value=_mock_json_response(mocker, {}),
    )

    assert creator.get_packing_groups("wf000") == []


def test_get_packing_group_id_returns_first_id(mocker):
    creator = InboundPlanCreator("token")
    mocker.patch(
        "infrastructure.amazon.inbound_plan_creator.httpx.get",
        return_value=_mock_json_response(
            mocker, {"packingOptions": [{"packingGroups": ["pg-aaa", "pg-bbb"]}]}
        ),
    )

    assert creator.get_packing_group_id("wf123") == "pg-aaa"
