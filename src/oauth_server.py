from __future__ import annotations

import os
from typing import Any
from urllib.parse import urlencode

import requests
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from dotenv import load_dotenv


load_dotenv()
app = FastAPI(title="Damccot Naver Works OAuth Callback")


def _env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def _required_env(name: str) -> str:
    value = _env(name)
    if not value:
        raise HTTPException(status_code=500, detail=f"Missing environment variable: {name}")
    return value


def _authorize_url(redirect_uri: str | None = None, state: str | None = None) -> str:
    params = {
        "response_type": "code",
        "client_id": _required_env("NAVER_WORKS_CLIENT_ID"),
        "redirect_uri": redirect_uri or _required_env("NAVER_WORKS_REDIRECT_URI"),
    }
    scope = _env("NAVER_WORKS_OAUTH_SCOPE")
    if scope:
        params["scope"] = scope
    state_value = state or _env("NAVER_WORKS_OAUTH_STATE")
    if state_value:
        params["state"] = state_value
    return f"{_env('NAVER_WORKS_AUTHORIZE_URL', 'https://auth.worksmobile.com/oauth2/v2.0/authorize')}?{urlencode(params)}"


def _verify_state(state: str | None) -> None:
    expected = _env("NAVER_WORKS_OAUTH_STATE")
    if expected and state != expected:
        raise HTTPException(status_code=400, detail="Invalid OAuth state.")


def _exchange_code(code: str, redirect_uri: str | None = None) -> dict[str, Any]:
    token_url = _env("NAVER_WORKS_TOKEN_URL", "https://auth.worksmobile.com/oauth2/v2.0/token")
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": _required_env("NAVER_WORKS_CLIENT_ID"),
        "client_secret": _required_env("NAVER_WORKS_CLIENT_SECRET"),
        "redirect_uri": redirect_uri or _required_env("NAVER_WORKS_REDIRECT_URI"),
    }
    response = requests.post(
        token_url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=20,
    )
    if not response.ok:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"Token exchange failed: {response.text[:500]}",
        )
    return response.json()


def _masked_token_response(payload: dict[str, Any]) -> dict[str, Any]:
    masked = dict(payload)
    for key in ("access_token", "refresh_token", "id_token"):
        value = masked.get(key)
        if isinstance(value, str):
            masked[key] = _mask_secret(value)
    return masked


def _mask_secret(value: str) -> str:
    if len(value) <= 12:
        return "***"
    return f"{value[:6]}...{value[-6:]}"


def _can_return_unmasked_token(payload: dict[str, Any], response_token: str | None) -> bool:
    expected = _env("OAUTH_UNMASKED_RESPONSE_TOKEN")
    requested = payload.get("masked") is False
    return bool(expected and response_token and response_token == expected and requested)


@app.get("/", response_class=PlainTextResponse)
def health() -> str:
    return "ok"


@app.get("/auth-url")
def auth_url(
    redirect_uri: str | None = Query(default=None),
    state: str | None = Query(default=None),
) -> dict[str, str]:
    return {"authUrl": _authorize_url(redirect_uri=redirect_uri, state=state)}


@app.get("/start", response_class=HTMLResponse)
def start() -> str:
    url = _authorize_url()
    return f"""<!doctype html>
<html lang="ko">
  <head><meta charset="utf-8"><title>Naver Works OAuth Start</title></head>
  <body>
    <p><a href="{url}">Start Naver Works OAuth</a></p>
  </body>
</html>"""


@app.get("/callback")
def callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
    exchange: bool = Query(default=False),
) -> JSONResponse:
    if error:
        return JSONResponse(
            status_code=400,
            content={"ok": False, "error": error, "error_description": error_description},
        )
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code.")
    _verify_state(state)

    should_exchange = exchange or _env("OAUTH_EXCHANGE_ON_CALLBACK").lower() == "true"
    if not should_exchange:
        return JSONResponse(
            {
                "ok": True,
                "state": state,
                "codeReceived": True,
                "next": "POST the callback URL code query parameter to /exchange.",
            }
        )

    token_payload = _exchange_code(code)
    return JSONResponse({"ok": True, "token": _masked_token_response(token_payload)})


@app.post("/exchange")
async def exchange(
    request: Request,
    x_oauth_response_token: str | None = Header(default=None),
) -> JSONResponse:
    payload = await request.json()
    code = payload.get("code")
    if not code:
        raise HTTPException(status_code=400, detail="Missing code in JSON body.")
    redirect_uri = payload.get("redirect_uri")
    token_payload = _exchange_code(str(code), str(redirect_uri) if redirect_uri else None)
    if _can_return_unmasked_token(payload, x_oauth_response_token):
        return JSONResponse({"ok": True, "token": token_payload})
    return JSONResponse({"ok": True, "token": _masked_token_response(token_payload)})
