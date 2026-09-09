from __future__ import annotations

import pytest

from infrastructure.amazon.inbound_plan_creator import InboundPlanCreator


class _Response:
    def __init__(self, status_code: int, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.text = "boom" if status_code >= 400 else "ok"

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import httpx
            raise httpx.HTTPStatusError("error", request=None, response=self)  # type: ignore[arg-type]


@pytest.fixture
def creator() -> InboundPlanCreator:
    return InboundPlanCreator(auth_token="dummy")


class TestPostAndWaitRetry:
    def test_一時的な400は再試行して成功させる(self, creator, monkeypatch) -> None:
        responses = [_Response(400), _Response(202, {"ok": True})]
        monkeypatch.setattr("infrastructure.amazon.inbound_plan_creator.time.sleep", lambda _s: None)
        monkeypatch.setattr(
            "infrastructure.amazon.inbound_plan_creator.httpx.post",
            lambda *a, **k: responses.pop(0),
        )
        assert creator._post_and_wait("http://x", {}) == {"ok": True}
        assert responses == []

    def test_400が続いたら最後は例外を投げる(self, creator, monkeypatch) -> None:
        import httpx
        monkeypatch.setattr("infrastructure.amazon.inbound_plan_creator.time.sleep", lambda _s: None)
        monkeypatch.setattr(
            "infrastructure.amazon.inbound_plan_creator.httpx.post",
            lambda *a, **k: _Response(400),
        )
        with pytest.raises(httpx.HTTPStatusError):
            creator._post_and_wait("http://x", {})

    def test_403は再試行せず即座に失敗する(self, creator, monkeypatch) -> None:
        import httpx
        calls: list[int] = []

        def post(*a, **k):
            calls.append(1)
            return _Response(403)

        monkeypatch.setattr("infrastructure.amazon.inbound_plan_creator.time.sleep", lambda _s: None)
        monkeypatch.setattr("infrastructure.amazon.inbound_plan_creator.httpx.post", post)
        with pytest.raises(httpx.HTTPStatusError):
            creator._post_and_wait("http://x", {})
        assert len(calls) == 1

    def test_成功時は再試行しない(self, creator, monkeypatch) -> None:
        calls: list[int] = []

        def post(*a, **k):
            calls.append(1)
            return _Response(202, {"done": 1})

        monkeypatch.setattr("infrastructure.amazon.inbound_plan_creator.httpx.post", post)
        assert creator._post_and_wait("http://x", {}) == {"done": 1}
        assert len(calls) == 1
