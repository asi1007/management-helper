from unittest.mock import patch, MagicMock
from infrastructure.amazon.fnsku_getter import FnskuGetter

class TestFnskuGetter:
    def test_get_fnsku_returns_value(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"summaries": [{"fnSku": "X001ABC123"}]}
        mock_response.raise_for_status = MagicMock()
        with patch("infrastructure.amazon.fnsku_getter.httpx.get", return_value=mock_response):
            getter = FnskuGetter(auth_token="dummy")
            result = getter.get_fnsku("MY-SKU-1")
        assert result == "X001ABC123"
