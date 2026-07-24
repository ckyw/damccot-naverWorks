#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.search_index import validate_index  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local SQLite-backed search UI.")
    parser.add_argument(
        "--index",
        type=Path,
        default=ROOT_DIR / "data/search/drive_search.sqlite",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    index_path = args.index.resolve()
    if not index_path.exists():
        parser.error(f"search index does not exist: {index_path}")
    validation = validate_index(index_path)
    if not validation.valid:
        parser.error(f"search index validation failed: {validation}")

    os.environ["SEARCH_INDEX_PATH"] = str(index_path)
    import uvicorn

    uvicorn.run(
        "src.search_ui:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        app_dir=str(ROOT_DIR),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
