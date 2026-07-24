from __future__ import annotations

import re
import unicodedata
from typing import Any


# Match folder names that commonly contain credentials. Matching is intentionally
# conservative: excluded folders and all descendants never enter output files.
SENSITIVE_FOLDER_MARKERS = {
    "아이디비번",
    "계정정보",
    "로그인정보",
    "접속정보",
    "인증정보",
    "password",
    "passwd",
    "credentials",
    "credential",
    "secret",
}


def is_sensitive_folder(item: dict[str, Any]) -> bool:
    if not item.get("isFolder"):
        return False
    name = str(item.get("fileName") or "").lower()
    normalized = re.sub(r"[\s_\-./]", "", name)
    return any(marker in normalized for marker in SENSITIVE_FOLDER_MARKERS)


def is_sensitive_path(path: str) -> bool:
    normalized = unicodedata.normalize("NFKC", str(path or "")).lower()
    normalized = re.sub(r"[\s_\-./\\]", "", normalized)
    return any(marker in normalized for marker in SENSITIVE_FOLDER_MARKERS)
