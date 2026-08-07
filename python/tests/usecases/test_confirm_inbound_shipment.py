from __future__ import annotations

import pytest

from usecases.confirm_inbound_shipment import (
    _find_other_carrier_option,
    _placement_fee_total,
)


def _transport_option(option_id: str, carrier_name: str, solution: str, mode: str) -> dict[str, object]:
    return {
        "transportationOptionId": option_id,
        "carrier": {"name": carrier_name},
        "shippingSolution": solution,
        "shippingMode": mode,
    }


class TestFindOtherCarrierOption:
    def test_その他かつ自社配送の小口配送を選ぶ(self) -> None:
        options = [
            _transport_option("to-yamato", "ヤマト運輸", "AMAZON_PARTNERED_CARRIER", "GROUND_SMALL_PARCEL"),
            _transport_option("to-sagawa", "佐川急便", "USE_YOUR_OWN_CARRIER", "GROUND_SMALL_PARCEL"),
            _transport_option("to-other", "Other", "USE_YOUR_OWN_CARRIER", "GROUND_SMALL_PARCEL"),
        ]
        assert _find_other_carrier_option(options)["transportationOptionId"] == "to-other"

    def test_Amazonパートナーキャリアのその他は選ばない(self) -> None:
        options = [
            _transport_option("to-partner", "Other", "AMAZON_PARTNERED_CARRIER", "GROUND_SMALL_PARCEL"),
        ]
        with pytest.raises(RuntimeError, match="その他"):
            _find_other_carrier_option(options)

    def test_小口配送以外のその他は選ばない(self) -> None:
        options = [
            _transport_option("to-ltl", "Other", "USE_YOUR_OWN_CARRIER", "FREIGHT_LTL"),
        ]
        with pytest.raises(RuntimeError, match="その他"):
            _find_other_carrier_option(options)


class TestPlacementFeeTotal:
    def test_手数料を合算する(self) -> None:
        option = {"fees": [
            {"value": {"amount": 1200, "code": "JPY"}},
            {"value": {"amount": 300, "code": "JPY"}},
        ]}
        assert _placement_fee_total(option) == 1500

    def test_手数料がなければゼロ(self) -> None:
        assert _placement_fee_total({"fees": []}) == 0
