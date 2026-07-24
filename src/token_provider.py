from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import requests


LOGGER = logging.getLogger(__name__)
TOKEN_URL = "https://auth.worksmobile.com/oauth2/v2.0/token"


class TokenRefreshError(RuntimeError):
    pass


@dataclass
class NaverWorksTokenProvider:
    """Supplies a valid access token without persisting short-lived tokens."""

    access_token: str = ""
    refresh_token: str = ""
    client_id: str = ""
    client_secret: str = ""
    token_url: str = TOKEN_URL
    refresh_leeway_seconds: int = 300
    persist_rotated_refresh_token: Callable[[str], None] | None = None

    _expires_at: float = field(default=0.0, init=False, repr=False)

    def get_access_token(self) -> str:
        if self.refresh_token:
            if not self.access_token or time.time() >= self._expires_at:
                self._refresh()
            return self.access_token
        if self.access_token:
            return self.access_token
        raise TokenRefreshError("No NAVER WORKS access token or refresh token is configured.")

    def invalidate_access_token(self) -> None:
        """Forces one fresh token request after an API 401 response."""
        self._expires_at = 0.0

    def _refresh(self) -> None:
        if not self.client_id or not self.client_secret:
            raise TokenRefreshError(
                "NAVER_WORKS_CLIENT_ID and NAVER_WORKS_CLIENT_SECRET are required "
                "when NAVER_WORKS_REFRESH_TOKEN is configured."
            )

        try:
            response = requests.post(
                self.token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": self.refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=20,
            )
        except requests.RequestException as exc:
            raise TokenRefreshError(f"Token refresh request failed: {exc}") from exc

        if not response.ok:
            raise TokenRefreshError(
                f"Token refresh failed ({response.status_code}): {response.text[:500]}"
            )

        payload: dict[str, Any] = response.json()
        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise TokenRefreshError("Token refresh response did not include access_token.")

        self.access_token = access_token
        expires_in = _positive_int(payload.get("expires_in"), default=3600)
        self._expires_at = time.time() + max(0, expires_in - self.refresh_leeway_seconds)

        rotated_token = payload.get("refresh_token")
        if isinstance(rotated_token, str) and rotated_token:
            if self.persist_rotated_refresh_token:
                try:
                    self.persist_rotated_refresh_token(rotated_token)
                except Exception as exc:
                    raise TokenRefreshError(
                        "Received a rotated refresh token but could not persist it."
                    ) from exc
                LOGGER.info("Persisted rotated NAVER WORKS refresh token.")
            else:
                LOGGER.warning(
                    "NAVER WORKS returned a rotated refresh token, but no Secret Manager resource is configured."
                )
            self.refresh_token = rotated_token


def _positive_int(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default
