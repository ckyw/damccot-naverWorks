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

from src.search_index import build_search_index_from_sources  # noqa: E402
from src.search_sources import load_source_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the local SQLite FTS5 search index.")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=ROOT_DIR / "config/search/sources.yaml",
    )
    parser.add_argument("--output", type=Path, default=ROOT_DIR / "data/search/drive_search.sqlite")
    parser.add_argument(
        "--taxonomy",
        type=Path,
        default=ROOT_DIR / "config/search/taxonomy_rules.yaml",
    )
    parser.add_argument(
        "--synonyms",
        type=Path,
        default=ROOT_DIR / "config/search/synonyms.yaml",
    )
    args = parser.parse_args()
    sources = load_source_manifest(args.manifest, base_dir=ROOT_DIR)
    stats = build_search_index_from_sources(
        sources,
        args.output,
        taxonomy_path=args.taxonomy,
        synonyms_path=args.synonyms,
    )
    print(json.dumps(asdict(stats), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
