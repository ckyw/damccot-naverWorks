from __future__ import annotations

import logging
import random
import time
from typing import Any

import requests

from src.token_provider import NaverWorksTokenProvider, TokenRefreshError


LOGGER = logging.getLogger(__name__)
BASE_URL = "https://www.worksapis.com/v1.0"
MAX_RETRIES = 6
RETRYABLE_STATUSES = {429, 500, 502, 503, 504}


class NaverWorksAPIError(RuntimeError):
    pass


def list_children(
    sharedrive_id: str,
    file_id: str | None,
    token_provider: NaverWorksTokenProvider,
    cursor: str | None = None,
    *,
    timeout: float = 20,
    request_sleep_seconds: float = 0.2,
) -> dict[str, Any]:
    url = (
        f"{BASE_URL}/sharedrives/{sharedrive_id}/files/{file_id}/children"
        if file_id
        else f"{BASE_URL}/sharedrives/{sharedrive_id}/files"
    )
    params: dict[str, Any] = {"count": 200, "orderBy": "filePath asc"}
    if cursor:
        params["cursor"] = cursor
    refreshed_after_unauthorized = False
    for attempt in range(1, MAX_RETRIES + 1):
        if request_sleep_seconds > 0:
            time.sleep(request_sleep_seconds)
        try:
            access_token = token_provider.get_access_token()
        except TokenRefreshError as exc:
            raise NaverWorksAPIError(f"Unable to obtain access token: {exc}") from exc
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            response = requests.get(url, headers=headers, params=params, timeout=timeout)
        except requests.RequestException as exc:
            if attempt == MAX_RETRIES:
                raise NaverWorksAPIError(f"Request failed after retries: {exc}") from exc
            _sleep_before_retry(attempt, "request_exception", file_id)
            continue

        if response.status_code == 401:
            if token_provider.refresh_token and not refreshed_after_unauthorized:
                refreshed_after_unauthorized = True
                token_provider.invalidate_access_token()
                continue
            raise NaverWorksAPIError("401 Unauthorized: access token may be expired.")
        if response.status_code in {403, 404}:
            LOGGER.warning(
                "Skipping folder due to API status",
                extra={"status": response.status_code, "file_id": file_id},
            )
            return {"files": [], "responseMetaData": {}}
        if response.status_code in RETRYABLE_STATUSES and attempt < MAX_RETRIES:
            _sleep_before_retry(
                attempt,
                str(response.status_code),
                file_id,
                retry_after=response.headers.get("Retry-After"),
            )
            continue
        if not response.ok:
            raise NaverWorksAPIError(
                f"Naver Works API error {response.status_code}: {response.text[:500]}"
            )
        return response.json()

    raise NaverWorksAPIError("Request retry loop ended unexpectedly.")


def _sleep_before_retry(
    attempt: int,
    reason: str,
    file_id: str | None,
    *,
    retry_after: str | None = None,
) -> None:
    delay = _retry_delay(attempt, retry_after)
    LOGGER.warning(
        "Retrying Naver Works API request after %.1f seconds (reason=%s, attempt=%s).",
        delay,
        reason,
        attempt,
    )
    time.sleep(delay)


def _retry_delay(attempt: int, retry_after: str | None) -> float:
    try:
        server_delay = float(retry_after) if retry_after else 0.0
    except ValueError:
        server_delay = 0.0
    exponential_delay = min(60.0, 2 ** (attempt - 1))
    # Small jitter prevents repeated clients from retrying in lockstep.
    return max(server_delay, exponential_delay) + random.uniform(0, 0.5)
