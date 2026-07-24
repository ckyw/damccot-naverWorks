from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any


FOLDER_TYPES = {"folder", "directory", "dir"}


def _lower(value: Any) -> str:
    return str(value or "").lower()


def is_folder_item(item: dict[str, Any]) -> bool:
    file_type = _lower(item.get("fileType") or item.get("type"))
    return file_type in FOLDER_TYPES or bool(item.get("folder"))


def extension_for(item: dict[str, Any]) -> str | None:
    if is_folder_item(item):
        return None
    name = str(item.get("fileName") or item.get("name") or "")
    suffix = PurePosixPath(name).suffix.lower().lstrip(".")
    return suffix or None


def normalize_item(
    item: dict[str, Any],
    *,
    depth: int,
    collected_at: str,
    parent_file_id: str | None = None,
) -> dict[str, Any]:
    return {
        "fileId": item.get("fileId") or item.get("id"),
        "parentFileId": item.get("parentFileId") or parent_file_id,
        "fileName": item.get("fileName") or item.get("name"),
        "filePath": item.get("filePath") or item.get("path"),
        "fileType": item.get("fileType") or item.get("type"),
        "fileSize": item.get("fileSize") or item.get("size") or 0,
        "createdTime": item.get("createdTime") or item.get("createdAt"),
        "modifiedTime": item.get("modifiedTime") or item.get("updatedAt"),
        "hasPermission": item.get("hasPermission"),
        "permissionRootFileId": item.get("permissionRootFileId"),
        "statuses": item.get("statuses") or [],
        "depth": depth,
        "extension": extension_for(item),
        "isFolder": is_folder_item(item),
        "collectedAt": collected_at,
    }

