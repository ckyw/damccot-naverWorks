#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.search_index import validate_index  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the local SQLite search index.")
    parser.add_argument(
        "--index",
        type=Path,
        default=ROOT_DIR / "data/search/drive_search.sqlite",
    )
    args = parser.parse_args()
    validation = validate_index(args.index)
    print(json.dumps(asdict(validation), ensure_ascii=False, indent=2))
    return 0 if validation.valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
