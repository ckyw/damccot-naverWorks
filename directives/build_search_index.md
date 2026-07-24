# Build Search Index

## Goal

Build a reproducible SQLite metadata database and FTS5 search index from a
NAVER WORKS Shared Drive tree JSON file.

## Inputs

- Source manifest: `config/search/sources.yaml`
- Raw tree JSON files: `data/sources/*/raw/sharedrive_tree_raw.json`
- Taxonomy rules: `config/search/taxonomy_rules.yaml`
- Synonyms: `config/search/synonyms.yaml`

## Output

- SQLite index: `data/search/drive_search.sqlite`

## Required Behavior

1. Preserve every raw JSON source without modification.
2. Normalize names, paths, extensions, and file types deterministically.
3. Exclude sensitive paths before writing any SQLite row.
4. Store taxonomy tags separately from document metadata.
5. Build an FTS5 index over names, paths, aliases, and tags.
6. Record every source, source count, and rule version in `index_metadata`.
7. Replace the output database atomically only after a successful build.

## Verification

- Compare total, indexed, invalid, duplicate, sensitive, and untagged counts.
- Confirm representative Korean substring searches return expected paths.
- Confirm no sensitive marker appears in stored document paths.
- Run `./execution/run_tests.sh` before using the generated index.
