from pathlib import Path

import pytest
from amazon_api import reset_shared_clients, shared_spapi_client
from amazon_api.testing import FakeSession, token_response

from infrastructure.amazon.auth import get_auth_token


@pytest.fixture(autouse=True)
def master(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "sp.env"
    path.write_text("API_KEY=cid\nAPI_SECRET=secret\nREFRESH_TOKEN=rt\n", encoding="utf-8")
    monkeypatch.setenv("SPAPI_CREDENTIALS_MASTER", str(path))
    reset_shared_clients()
    yield
    reset_shared_clients()


class TestGetAuthToken:
    def test_共有マスターのトークンを返す(self):
        session = FakeSession([token_response(access_token="test-token-123")])
        shared_spapi_client(session=session)

        assert get_auth_token() == "test-token-123"

    def test_二度目はLWAを叩かない(self):
        session = FakeSession([token_response()])
        shared_spapi_client(session=session)

        get_auth_token()
        get_auth_token()

        assert len(session.urls_of("auth/o2/token")) == 1
