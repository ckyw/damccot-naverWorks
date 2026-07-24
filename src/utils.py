from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


KST = timezone(timedelta(hours=9))


def utc_now_iso() -> str:
    return datetime.now(KST).isoformat(timespec="seconds")


def ensure_output_dirs(output_dir: Path) -> None:
    for child in ("raw", "batches", "reports"):
        (output_dir / child).mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
