from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any

from src.naverworks_client import list_children
from src.normalizer import normalize_item
from src.sensitive_filter import is_sensitive_folder
from src.token_provider import NaverWorksTokenProvider
from src.utils import utc_now_iso


LOGGER = logging.getLogger(__name__)


def _extract_children(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("files", "items", "children", "data"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    if isinstance(payload.get("fileList"), list):
        return payload["fileList"]
    return []


def _extract_next_cursor(payload: dict[str, Any]) -> str | None:
    metadata = payload.get("responseMetaData") or payload.get("meta") or {}
    return metadata.get("nextCursor") or payload.get("nextCursor")


def collect_drive_tree(
    sharedrive_id: str,
    root_file_id: str | None,
    token_provider: NaverWorksTokenProvider,
    max_depth: int | None = None,
    *,
    request_sleep_seconds: float = 0.2,
) -> list[dict[str, Any]]:
    collected_at = utc_now_iso()
    items: list[dict[str, Any]] = []
    queue: deque[tuple[str | None, int]] = deque([(root_file_id, 0)])
    visited_folders: set[str | None] = set()

    LOGGER.info(
        "Starting shared drive collection",
        extra={"sharedrive_id": sharedrive_id, "root_file_id": root_file_id},
    )

    while queue:
        folder_id, depth = queue.popleft()
        if folder_id in visited_folders:
            continue
        visited_folders.add(folder_id)

        if max_depth is not None and depth >= max_depth:
            LOGGER.info("Reached max depth", extra={"folder_id": folder_id, "depth": depth})
            continue

        cursor: str | None = None
        page_count = 0
        while True:
            payload = list_children(
                sharedrive_id,
                folder_id,
                token_provider,
                cursor,
                request_sleep_seconds=request_sleep_seconds,
            )
            children = _extract_children(payload)
            page_count += 1
            LOGGER.info(
                "Collected children page",
                extra={
                    "folder_id": folder_id,
                    "depth": depth,
                    "page": page_count,
                    "children": len(children),
                },
            )

            for child in children:
                normalized = normalize_item(
                    child,
                    depth=depth + 1,
                    collected_at=collected_at,
                    parent_file_id=folder_id,
                )
                if is_sensitive_folder(normalized):
                    LOGGER.info("Excluded a sensitive folder and its descendants.")
                    continue
                items.append(normalized)
                child_id = normalized.get("fileId")
                if normalized["isFolder"] and child_id:
                    queue.append((str(child_id), depth + 1))

            cursor = _extract_next_cursor(payload)
            if not cursor:
                break

    LOGGER.info(
        "Finished shared drive collection",
        extra={"folders_visited": len(visited_folders), "total_items": len(items)},
    )
    return items
