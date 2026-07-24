from __future__ import annotations

from src import naverworks_client
from src.secret_manager import RefreshTokenSecretStore
from src.token_provider import NaverWorksTokenProvider


class FakeResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload
        self.text = "error"

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    def json(self) -> dict:
        return self._payload


def test_refresh_token_issues_an_access_token(monkeypatch):
    captured = {}

    def fake_post(*args, **kwargs):
        captured.update(kwargs)
        return FakeResponse(200, {"access_token": "fresh-access-token", "expires_in": "3600"})

    monkeypatch.setattr("src.token_provider.requests.post", fake_post)
    provider = NaverWorksTokenProvider(
        refresh_token="refresh-token",
        client_id="client-id",
        client_secret="client-secret",
    )

    assert provider.get_access_token() == "fresh-access-token"
    assert captured["data"]["grant_type"] == "refresh_token"
    assert captured["data"]["refresh_token"] == "refresh-token"


def test_api_retries_once_after_unauthorized_with_refreshed_token(monkeypatch):
    class FakeProvider:
        refresh_token = "refresh-token"

        def __init__(self):
            self.invalidated = False

        def get_access_token(self):
            return "fresh-token" if self.invalidated else "expired-token"

        def invalidate_access_token(self):
            self.invalidated = True

    responses = [
        FakeResponse(401, {}),
        FakeResponse(200, {"files": [{"fileId": "folder-1"}]}),
    ]

    def fake_get(*args, **kwargs):
        return responses.pop(0)

    monkeypatch.setattr(naverworks_client.requests, "get", fake_get)
    provider = FakeProvider()

    payload = naverworks_client.list_children("drive-id", "folder-id", provider)

    assert payload == {"files": [{"fileId": "folder-1"}]}
    assert provider.invalidated is True


def test_rotated_refresh_token_is_persisted(monkeypatch):
    monkeypatch.setattr(
        "src.token_provider.requests.post",
        lambda *args, **kwargs: FakeResponse(
            200,
            {
                "access_token": "fresh-access-token",
                "refresh_token": "rotated-refresh-token",
                "expires_in": 3600,
            },
        ),
    )
    stored = []
    provider = NaverWorksTokenProvider(
        refresh_token="refresh-token",
        client_id="client-id",
        client_secret="client-secret",
        persist_rotated_refresh_token=stored.append,
    )

    provider.get_access_token()

    assert stored == ["rotated-refresh-token"]
    assert provider.refresh_token == "rotated-refresh-token"


def test_secret_manager_store_adds_a_new_secret_version(monkeypatch):
    captured = {}

    class FakeSecretManagerClient:
        def add_secret_version(self, request):
            captured.update(request)

    monkeypatch.setattr(
        "src.secret_manager.secretmanager.SecretManagerServiceClient",
        FakeSecretManagerClient,
    )

    RefreshTokenSecretStore("projects/test-project/secrets/refresh-token").persist("new-token")

    assert captured["parent"] == "projects/test-project/secrets/refresh-token"
    assert captured["payload"]["data"] == b"new-token"


def test_retry_delay_prefers_the_server_retry_after(monkeypatch):
    monkeypatch.setattr(naverworks_client.random, "uniform", lambda _start, _end: 0.0)

    assert naverworks_client._retry_delay(1, "12") == 12.0
    assert naverworks_client._retry_delay(3, None) == 4.0
