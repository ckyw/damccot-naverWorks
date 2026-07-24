from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from src.search_documents import normalize_search_text
from src.search_index import (
    build_search_index,
    build_search_index_from_sources,
    index_metadata,
    parse_query,
    search_index,
    validate_index,
)
from src.search_sources import SearchSource, load_source_manifest
from src.sensitive_filter import is_sensitive_path


ROOT_DIR = Path(__file__).resolve().parents[1]
TAXONOMY_PATH = ROOT_DIR / "config/search/taxonomy_rules.yaml"
SYNONYMS_PATH = ROOT_DIR / "config/search/synonyms.yaml"


def _build_fixture_index(tmp_path: Path) -> Path:
    raw_path = tmp_path / "tree.json"
    raw_path.write_text(
        json.dumps(
            {
                "collectedAt": "2026-07-21T00:00:00+09:00",
                "sharedriveId": "@drive",
                "items": [
                    {
                        "fileId": "1",
                        "fileName": "팥바팥빙수.jpg",
                        "filePath": "/이미지/상품/빙수/팥바팥빙수.jpg",
                        "fileType": "IMAGE",
                        "extension": "jpg",
                        "isFolder": False,
                        "modifiedTime": "2026-07-20T00:00:00+09:00",
                    },
                    {
                        "fileId": "2",
                        "fileName": "HACCP 점검표.pdf",
                        "filePath": "/품질/HACCP 점검표.pdf",
                        "fileType": "DOC",
                        "extension": "pdf",
                        "isFolder": False,
                    },
                    {
                        "fileId": "3",
                        "fileName": "매장 시안.psd",
                        "filePath": "/디자인/매장/매장 시안.psd",
                        "fileType": "ETC",
                        "extension": "psd",
                        "isFolder": False,
                    },
                    {
                        "fileId": "4",
                        "fileName": "password.txt",
                        "filePath": "/아이디 비번/password.txt",
                        "fileType": "DOC",
                        "extension": "txt",
                        "isFolder": False,
                    },
                    {
                        "fileId": "6",
                        "fileName": "randomEQcIdentifier.jpg",
                        "filePath": "/이미지/randomEQcIdentifier.jpg",
                        "fileType": "IMAGE",
                        "extension": "jpg",
                        "isFolder": False,
                    },
                    {"fileId": "5", "fileName": "경로 없음"},
                    {
                        "fileId": "1",
                        "fileName": "중복.jpg",
                        "filePath": "/중복.jpg",
                        "fileType": "IMAGE",
                        "isFolder": False,
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    index_path = tmp_path / "search.sqlite"
    stats = build_search_index(
        raw_path,
        index_path,
        taxonomy_path=TAXONOMY_PATH,
        synonyms_path=SYNONYMS_PATH,
    )
    assert stats.total_items == 7
    assert stats.indexed_items == 4
    assert stats.sensitive_excluded == 1
    assert stats.invalid_excluded == 1
    assert stats.duplicate_excluded == 1
    return index_path


def test_normalization_and_sensitive_path_detection():
    assert normalize_search_text("  HACCP_점검표.PDF ") == "haccp 점검표 pdf"
    assert is_sensitive_path("/운영/아이디 비번/접속.txt") is True
    assert is_sensitive_path("/품질/HACCP/점검표.pdf") is False


def test_builds_metadata_tables_and_fts5(tmp_path):
    index_path = _build_fixture_index(tmp_path)
    metadata = index_metadata(index_path)
    assert metadata["indexed_items"] == "4"
    assert metadata["taxonomy_version"] == "1"

    with sqlite3.connect(index_path) as connection:
        document_count = connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
        fts_count = connection.execute("SELECT COUNT(*) FROM documents_fts").fetchone()[0]
        sensitive_count = connection.execute(
            "SELECT COUNT(*) FROM documents WHERE file_path LIKE '%비번%'"
        ).fetchone()[0]
    assert document_count == 4
    assert fts_count == 4
    assert sensitive_count == 0
    validation = validate_index(index_path)
    assert validation.valid is True
    assert validation.sensitive_path_count == 0


def test_search_supports_korean_substrings_synonyms_and_filters(tmp_path):
    index_path = _build_fixture_index(tmp_path)

    substring_results = search_index(index_path, "빙수")
    assert substring_results[0].file_name == "팥바팥빙수.jpg"

    synonym_results = search_index(index_path, "사진")
    assert synonym_results[0].file_name == "팥바팥빙수.jpg"

    filtered_results = search_index(index_path, "점검표 ext:pdf tag:품질관리")
    assert [result.file_name for result in filtered_results] == ["HACCP 점검표.pdf"]

    haccp_results = search_index(index_path, "HACCP")
    assert [result.file_name for result in haccp_results] == ["HACCP 점검표.pdf"]

    assert search_index(index_path, "type:video") == []


def test_parse_query_tolerates_unclosed_quotes():
    parsed = parse_query('"빙수 사진')

    assert parsed.text == '"빙수 사진'


def test_manifest_build_combines_distinct_shared_drives(tmp_path):
    source_paths: list[Path] = []
    for name, drive_id, file_path in (
        ("image-assets", "@images", "/이미지/빙수.jpg"),
        ("quality-management", "@quality", "/품질관리/HACCP 점검표.pdf"),
    ):
        raw_path = tmp_path / name / "raw" / "sharedrive_tree_raw.json"
        raw_path.parent.mkdir(parents=True)
        raw_path.write_text(
            json.dumps(
                {
                    "sharedriveId": drive_id,
                    "items": [
                        {
                            "fileId": "same-file-id",
                            "fileName": Path(file_path).name,
                            "filePath": file_path,
                            "fileType": "DOC" if file_path.endswith(".pdf") else "IMAGE",
                            "isFolder": False,
                        }
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        source_paths.append(raw_path)

    manifest_path = tmp_path / "sources.yaml"
    manifest_path.write_text(
        "version: 1\nsources:\n"
        "  - name: image-assets\n    path: image-assets/raw/sharedrive_tree_raw.json\n"
        "  - name: quality-management\n    path: quality-management/raw/sharedrive_tree_raw.json\n",
        encoding="utf-8",
    )
    sources = load_source_manifest(manifest_path, base_dir=tmp_path)
    assert sources == (
        SearchSource(name="image-assets", path=source_paths[0].resolve()),
        SearchSource(name="quality-management", path=source_paths[1].resolve()),
    )

    index_path = tmp_path / "combined.sqlite"
    stats = build_search_index_from_sources(
        sources,
        index_path,
        taxonomy_path=TAXONOMY_PATH,
        synonyms_path=SYNONYMS_PATH,
    )
    metadata = index_metadata(index_path)

    assert stats.total_items == 2
    assert stats.indexed_items == 2
    assert metadata["source_count"] == "2"
    assert [result.file_name for result in search_index(index_path, "HACCP")] == [
        "HACCP 점검표.pdf"
    ]
