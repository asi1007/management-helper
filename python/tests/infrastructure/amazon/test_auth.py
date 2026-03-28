from unittest.mock import patch, MagicMock
import pytest
from infrastructure.amazon.auth import get_auth_token

class TestGetAuthToken:
    def test_returns_access_token(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"access_token": "test-token-123"}
        mock_response.raise_for_status = MagicMock()
        with patch("infrastructure.amazon.auth.httpx.post", return_value=mock_response):
            token = get_auth_token(api_key="key", api_secret="secret", refresh_token="refresh")
        assert token == "test-token-123"

    def test_raises_on_missing_token(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {}
        mock_response.raise_for_status = MagicMock()
        with patch("infrastructure.amazon.auth.httpx.post", return_value=mock_response):
            with pytest.raises(KeyError):
                get_auth_token(api_key="key", api_secret="secret", refresh_token="refresh")
