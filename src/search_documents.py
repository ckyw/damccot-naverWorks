from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from src.sensitive_filter import is_sensitive_path


SEPARATORS = re.compile(r"[/\\_.\-()\[\]{}]+")
WHITESPACE = re.compile(r"\s+")


def normalize_search_text(value: Any) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or "")).lower()
    normalized = SEPARATORS.sub(" ", normalized)
    return WHITESPACE.sub(" ", normalized).strip()


def search_text_contains(searchable_text: str, term: str) -> bool:
    if not term:
        return False
    if any("가" <= character <= "힣" for character in term) or len(term) >= 4:
        return term in searchable_text
    return term in searchable_text.split()


@dataclass(frozen=True)
class SearchDocument:
    document_key: str
    source_drive_id: str
    source_drive_name: str
    file_id: str
    parent_file_id: str
    file_name: str
    normalized_name: str
    file_path: str
    normalized_path: str
    file_type: str
    extension: str
    is_folder: bool
    modified_time: str

    @property
    def searchable_text(self) -> str:
        return f"{self.normalized_name} {self.normalized_path}".strip()


def document_from_item(
    item: dict[str, Any],
    *,
    source_drive_id: str,
    source_drive_name: str,
) -> SearchDocument | None:
    file_name = str(item.get("fileName") or "").strip()
    file_path = str(item.get("filePath") or "").strip()
    if not file_name or not file_path or is_sensitive_path(file_path):
        return None

    file_id = str(item.get("fileId") or "").strip()
    document_key = f"{source_drive_id}:{file_id or file_path}"
    is_folder = bool(item.get("isFolder"))
    extension = str(item.get("extension") or "").lower().lstrip(".")
    if not extension and not is_folder:
        extension = PurePosixPath(file_name).suffix.lower().lstrip(".")

    return SearchDocument(
        document_key=document_key,
        source_drive_id=source_drive_id,
        source_drive_name=source_drive_name,
        file_id=file_id,
        parent_file_id=str(item.get("parentFileId") or ""),
        file_name=file_name,
        normalized_name=normalize_search_text(file_name),
        file_path=file_path,
        normalized_path=normalize_search_text(file_path),
        file_type=str(item.get("fileType") or "").lower(),
        extension=extension,
        is_folder=is_folder,
        modified_time=str(item.get("modifiedTime") or ""),
    )
