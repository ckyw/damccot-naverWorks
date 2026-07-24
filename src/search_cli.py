from __future__ import annotations

import argparse
import json
from pathlib import Path

from src.search_index import search_index


def main() -> int:
    parser = argparse.ArgumentParser(description="Search the local NAVER WORKS SQLite index.")
    parser.add_argument("query", help="Search text and optional type:, ext:, or tag: filters")
    parser.add_argument("--index", type=Path, default=Path("data/search/drive_search.sqlite"))
    parser.add_argument("--limit", type=int, default=10)
    args = parser.parse_args()
    results = search_index(args.index, args.query, limit=args.limit)
    print(json.dumps([result.as_dict() for result in results], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
