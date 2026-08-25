"""試作プランのキャンセルのテスト"""
from __future__ import annotations

from infrastructure.amazon.inbound_plan_creator import InboundPlanCreator


def test_cancellationエンドポイントをPUTで叩く(mocker):
    creator = InboundPlanCreator("token")
    resp = mocker.Mock()
    resp.json.return_value = {}
    resp.raise_for_status = mocker.Mock()
    mock_put = mocker.patch(
        "infrastructure.amazon.inbound_plan_creator.httpx.put", return_value=resp
    )

    creator.cancel_inbound_plan("wf123")

    called_url = mock_put.call_args[0][0]
    assert called_url.endswith("/inboundPlans/wf123/cancellation")


def test_operationIdが返れば完了を待つ(mocker):
    creator = InboundPlanCreator("token")
    resp = mocker.Mock()
    resp.json.return_value = {"operationId": "op-1"}
    resp.raise_for_status = mocker.Mock()
    mocker.patch("infrastructure.amazon.inbound_plan_creator.httpx.put", return_value=resp)
    wait = mocker.patch.object(InboundPlanCreator, "_wait_operation", return_value={"operationStatus": "SUCCESS"})

    creator.cancel_inbound_plan("wf123")

    wait.assert_called_once_with("op-1")
