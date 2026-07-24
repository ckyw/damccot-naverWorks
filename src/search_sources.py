from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class SearchSource:
    name: str
    path: Path


def load_source_manifest(manifest_path: Path, *, base_dir: Path) -> tuple[SearchSource, ...]:
    payload: Any = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("sources"), list):
        raise ValueError("Source manifest must contain a sources list")

    sources: list[SearchSource] = []
    names: set[str] = set()
    paths: set[Path] = set()
    for entry in payload["sources"]:
        if not isinstance(entry, dict):
            raise ValueError("Each source entry must be a mapping")
        name = str(entry.get("name") or "").strip()
        path_value = str(entry.get("path") or "").strip()
        if not name or not path_value:
            raise ValueError("Each source requires name and path")
        path = Path(path_value)
        if not path.is_absolute():
            path = base_dir / path
        path = path.resolve()
        if name in names:
            raise ValueError(f"Duplicate source name: {name}")
        if path in paths:
            raise ValueError(f"Duplicate source path: {path}")
        if not path.is_file():
            raise FileNotFoundError(path)
        names.add(name)
        paths.add(path)
        sources.append(SearchSource(name=name, path=path))
    if not sources:
        raise ValueError("Source manifest must contain at least one source")
    return tuple(sources)
