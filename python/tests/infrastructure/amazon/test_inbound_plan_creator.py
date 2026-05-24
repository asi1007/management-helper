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
