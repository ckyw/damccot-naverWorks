import json

from src import oauth_server


def _json_response_body(response):
    return json.loads(response.body.decode("utf-8"))


def test_callback_does_not_return_authorization_code(monkeypatch):
    monkeypatch.setenv("OAUTH_EXCHANGE_ON_CALLBACK", "false")
    monkeypatch.setenv("NAVER_WORKS_OAUTH_STATE", "expected-state")

    response = oauth_server.callback(
        code="secret-code",
        state="expected-state",
        error=None,
        error_description=None,
        exchange=False,
    )
    body = _json_response_body(response)

    assert body["ok"] is True
    assert body["codeReceived"] is True
    assert "code" not in body


def test_callback_exchange_returns_masked_token(monkeypatch):
    monkeypatch.setenv("NAVER_WORKS_OAUTH_STATE", "expected-state")
    monkeypatch.setattr(
        oauth_server,
        "_exchange_code",
        lambda code: {
            "access_token": "access-token-value",
            "refresh_token": "refresh-token-value",
            "expires_in": 3600,
        },
    )

    response = oauth_server.callback(
        code="secret-code",
        state="expected-state",
        error=None,
        error_description=None,
        exchange=True,
    )
    body = _json_response_body(response)

    assert body["token"]["access_token"] == "access...-value"
    assert body["token"]["refresh_token"] == "refres...-value"
    assert body["token"]["expires_in"] == 3600


def test_unmasked_token_response_requires_shared_response_token(monkeypatch):
    payload = {"masked": False}

    monkeypatch.delenv("OAUTH_UNMASKED_RESPONSE_TOKEN", raising=False)
    assert oauth_server._can_return_unmasked_token(payload, "token") is False

    monkeypatch.setenv("OAUTH_UNMASKED_RESPONSE_TOKEN", "expected-token")
    assert oauth_server._can_return_unmasked_token(payload, "wrong-token") is False
    assert oauth_server._can_return_unmasked_token(payload, "expected-token") is True
