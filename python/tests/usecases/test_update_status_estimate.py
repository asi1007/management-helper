from usecases.update_status_estimate import _extract_plan_identifier, _is_received


def test_extract_plan_identifier_from_summary_url():
    cell = '=HYPERLINK("https://sellercentral.amazon.co.jp/fba/inbound-shipment/summary/FBA15GBW843C","FBA15GBW843C")'
    assert _extract_plan_identifier(cell) == {"shipmentId": "FBA15GBW843C"}


def test_extract_plan_identifier_truncates_extra_digits():
    cell = '=HYPERLINK("https://sellercentral.amazon.co.jp/fba/inbound-shipment/summary/FBA15GBW843C765234","FBA15GBW843C765234")'
    assert _extract_plan_identifier(cell) == {"shipmentId": "FBA15GBW843C"}


def test_extract_plan_identifier_from_workflow_url():
    cell = '=HYPERLINK("https://sellercentral.amazon.co.jp/fba/sendtoamazon/workflow/continue?wf=wfabc123def456","plan")'
    assert _extract_plan_identifier(cell) == {"inboundPlanId": "wfabc123def456"}


def test_extract_plan_identifier_plain_shipment_id():
    assert _extract_plan_identifier("FBA15GBW843C") == {"shipmentId": "FBA15GBW843C"}


def test_extract_plan_identifier_empty():
    assert _extract_plan_identifier("") is None


def test_extract_plan_identifier_no_id():
    assert _extract_plan_identifier("梱包依頼済み") is None


def test_is_received_closed_with_shipped():
    assert _is_received("CLOSED", 1000, 0) is True


def test_is_received_closed_without_shipped():
    assert _is_received("CLOSED", 0, 0) is False


def test_is_received_high_receive_ratio():
    assert _is_received("DELIVERED", 1500, 1466) is True


def test_is_received_low_receive_ratio():
    assert _is_received("DELIVERED", 1000, 800) is False


def test_is_received_zero_received():
    assert _is_received("DELIVERED", 88, 0) is False
