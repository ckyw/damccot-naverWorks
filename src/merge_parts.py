from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.batcher import write_batches
from src.reporter import write_reports
from src.tree_exports import write_tree_exports
from src.utils import ensure_output_dirs, utc_now_iso, write_json


def merge_part_items(parts_dir: Path) -> list[dict[str, Any]]:
    unique_items: dict[str, dict[str, Any]] = {}
    for path in sorted(parts_dir.glob("*/raw/sharedrive_tree_raw.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload.get("items", []):
            if not isinstance(item, dict):
                continue
            key = str(item.get("fileId") or f"{item.get('filePath')}:{item.get('fileName')}")
            unique_items[key] = item
    return sorted(
        unique_items.values(),
        key=lambda item: (str(item.get("filePath") or ""), str(item.get("fileName") or "")),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Merge per-folder Shared Drive collection parts.")
    parser.add_argument("--parts-dir", default="data/sources/default/parts")
    parser.add_argument("--output-dir", default="data/sources/default")
    parser.add_argument("--sharedrive-id", required=True)
    args = parser.parse_args()

    parts_dir = Path(args.parts_dir)
    output_dir = Path(args.output_dir)
    items = merge_part_items(parts_dir)
    if not items:
        raise SystemExit(f"No collection parts found under {parts_dir}.")

    ensure_output_dirs(output_dir)
    payload = {
        "collectedAt": utc_now_iso(),
        "sharedriveId": args.sharedrive_id,
        "rootFileId": None,
        "totalItems": len(items),
        "items": items,
    }
    write_json(output_dir / "raw" / "sharedrive_tree_raw.json", payload)
    write_tree_exports(items, output_dir)
    write_reports(items, output_dir)
    write_batches(items, output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
