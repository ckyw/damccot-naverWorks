from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from src.utils import write_text


CSV_COLUMNS = (
    "fileName",
    "filePath",
    "fileType",
    "extension",
    "isFolder",
    "depth",
    "fileSize",
    "createdTime",
    "modifiedTime",
)


def write_tree_exports(items: list[dict[str, Any]], output_dir: Path) -> None:
    reports_dir = output_dir / "reports"
    _write_tree_csv(reports_dir / "sharedrive_tree.csv", items)
    write_text(reports_dir / "folder_tree.md", folder_tree_markdown(items))


def _write_tree_csv(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for item in sorted(items, key=_tree_sort_key):
            writer.writerow({column: _csv_value(item.get(column)) for column in CSV_COLUMNS})


def folder_tree_markdown(items: list[dict[str, Any]]) -> str:
    lines = ["# Shared Drive Folder Tree", ""]
    for item in sorted(items, key=_tree_sort_key):
        depth = max(1, int(item.get("depth") or 1))
        indent = "  " * (depth - 1)
        kind = "folder" if item.get("isFolder") else "file"
        name = str(item.get("fileName") or "(unnamed)").replace("\n", " ")
        lines.append(f"{indent}- [{kind}] {name}")
    return "\n".join(lines) + "\n"


def _tree_sort_key(item: dict[str, Any]) -> tuple[str, int, str]:
    return (
        str(item.get("filePath") or ""),
        0 if item.get("isFolder") else 1,
        str(item.get("fileName") or ""),
    )


def _csv_value(value: Any) -> Any:
    if isinstance(value, str) and value.startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value
