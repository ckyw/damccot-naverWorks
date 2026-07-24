import json
from pathlib import Path

import pytest
from fastapi import Response

from src import search_ui
from src.search_index import build_search_index


ROOT_DIR = Path(__file__).resolve().parents[1]
TAXONOMY_PATH = ROOT_DIR / "config/search/taxonomy_rules.yaml"
SYNONYMS_PATH = ROOT_DIR / "config/search/synonyms.yaml"


def test_search_returns_path_and_excludes_sensitive_items(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    raw_path = tmp_path / "tree.json"
    raw_path.write_text(
        json.dumps(
            {
                "sharedriveId": "@quality",
                "items": [
                    {
                        "fileId": "1",
                        "fileName": "HACCP 점검표.xlsx",
                        "filePath": "/품질/HACCP 점검표.xlsx",
                        "fileType": "DOC",
                        "extension": "xlsx",
                        "isFolder": False,
                    },
                    {
                        "fileId": "2",
                        "fileName": "password.xlsx",
                        "filePath": "/아이디비번/password.xlsx",
                        "fileType": "DOC",
                        "extension": "xlsx",
                        "isFolder": False,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    index = tmp_path / "index.sqlite"
    build_search_index(
        raw_path,
        index,
        taxonomy_path=TAXONOMY_PATH,
        synonyms_path=SYNONYMS_PATH,
    )
    monkeypatch.setenv("SEARCH_INDEX_PATH", str(index))

    results = search_ui.search_items("HACCP")

    assert len(results) == 1
    assert results[0]["fileName"] == "HACCP 점검표.xlsx"
    assert results[0]["filePath"] == "/품질/HACCP 점검표.xlsx"
    assert results[0]["extension"] == "xlsx"
    assert results[0]["tags"]


def test_health_reports_sqlite_metadata(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    raw_path = tmp_path / "tree.json"
    raw_path.write_text(
        json.dumps(
            {
                "sharedriveId": "@images",
                "items": [
                    {
                        "fileId": "1",
                        "fileName": "빙수.jpg",
                        "filePath": "/이미지/빙수.jpg",
                        "fileType": "IMAGE",
                        "isFolder": False,
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    index = tmp_path / "index.sqlite"
    build_search_index(
        raw_path,
        index,
        taxonomy_path=TAXONOMY_PATH,
        synonyms_path=SYNONYMS_PATH,
    )
    monkeypatch.setenv("SEARCH_INDEX_PATH", str(index))

    response = Response()
    assert search_ui.healthz(response) == {
        "status": "ok",
        "index": "ready",
        "documents": 1,
        "sources": 1,
        "queryAnalyzer": "fallback",
    }
    assert response.status_code == 200


def test_health_returns_503_when_index_is_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("SEARCH_INDEX_PATH", str(tmp_path / "missing.sqlite"))
    response = Response()

    assert search_ui.healthz(response) == {"status": "degraded", "index": "missing"}
    assert response.status_code == 503


def test_startup_validation_rejects_missing_index(tmp_path, monkeypatch):
    monkeypatch.setenv("SEARCH_INDEX_PATH", str(tmp_path / "missing.sqlite"))

    with pytest.raises(RuntimeError, match="cannot be opened"):
        search_ui._validate_runtime_index()


def test_vercel_entrypoint_exposes_the_search_app():
    from src.app import app

    assert app.title == "Damccot Drive Search"
