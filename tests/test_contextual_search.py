from __future__ import annotations

import json
from pathlib import Path

from src.contextual_search import contextual_search
from src.query_understanding import QueryPlan
from src.search_index import build_search_index


ROOT_DIR = Path(__file__).resolve().parents[1]
TAXONOMY_PATH = ROOT_DIR / "config/search/taxonomy_rules.yaml"
SYNONYMS_PATH = ROOT_DIR / "config/search/synonyms.yaml"


def _query_plan(query: str) -> QueryPlan:
    return QueryPlan(
        original_query=query,
        cleaned_query="롯데홈쇼핑 원산지 제출 문서",
        entities=("롯데홈쇼핑",),
        topics=("원산지",),
        document_types=("문서",),
        actions=("제출",),
        keywords=("롯데홈쇼핑", "원산지", "제출"),
        required_terms=("롯데홈쇼핑",),
        preferred_terms=("원산지", "제출"),
        confidence=0.9,
        analyzer="test",
    )


def test_contextual_search_requires_entity_and_groups_by_matching_folder(tmp_path):
    raw_path = tmp_path / "tree.json"
    raw_path.write_text(
        json.dumps(
            {
                "sharedriveId": "@quality",
                "items": [
                    {
                        "fileId": "1",
                        "fileName": "원산지확약서.pdf",
                        "filePath": "/품질/롯데홈쇼핑/제출자료/원산지확약서.pdf",
                        "fileType": "DOC",
                        "extension": "pdf",
                        "isFolder": False,
                    },
                    {
                        "fileId": "2",
                        "fileName": "원산지증명서.pdf",
                        "filePath": "/품질/다른고객사/원산지증명서.pdf",
                        "fileType": "DOC",
                        "extension": "pdf",
                        "isFolder": False,
                    },
                    {
                        "fileId": "3",
                        "fileName": "롯데홈쇼핑 영상.mp4",
                        "filePath": "/이미지/롯데홈쇼핑/롯데홈쇼핑 영상.mp4",
                        "fileType": "VIDEO",
                        "extension": "mp4",
                        "isFolder": False,
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    index_path = tmp_path / "search.sqlite"
    build_search_index(
        raw_path,
        index_path,
        taxonomy_path=TAXONOMY_PATH,
        synonyms_path=SYNONYMS_PATH,
    )

    outcome = contextual_search(
        index_path,
        "롯데홈쇼핑에 제출한 원산지 문서는 어디에?",
        analyzer=_query_plan,
    )

    paths = [item.result.file_path for item in outcome.results]
    assert paths[0] == "/품질/롯데홈쇼핑/제출자료/원산지확약서.pdf"
    assert all("롯데홈쇼핑" in path for path in paths)
    assert "/품질/다른고객사/원산지증명서.pdf" not in paths
    assert outcome.groups[0].folder_path == "/품질/롯데홈쇼핑/"
    assert outcome.required_terms_relaxed is False


def test_contextual_search_prefers_term_coverage_without_required_terms(tmp_path):
    raw_path = tmp_path / "tree.json"
    raw_path.write_text(
        json.dumps(
            {
                "sharedriveId": "@quality",
                "items": [
                    {
                        "fileId": "1",
                        "fileName": "원산지",
                        "filePath": "/법규/원산지/",
                        "fileType": "FOLDER",
                        "isFolder": True,
                    },
                    {
                        "fileId": "2",
                        "fileName": "원산지확약서.pdf",
                        "filePath": "/고객사/롯데홈쇼핑/원산지확약서.pdf",
                        "fileType": "DOC",
                        "extension": "pdf",
                        "isFolder": False,
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    index_path = tmp_path / "search.sqlite"
    build_search_index(
        raw_path,
        index_path,
        taxonomy_path=TAXONOMY_PATH,
        synonyms_path=SYNONYMS_PATH,
    )
    plan = QueryPlan(
        original_query="롯데홈쇼핑 원산지",
        cleaned_query="롯데홈쇼핑 원산지",
        entities=(),
        topics=("롯데홈쇼핑", "원산지"),
        document_types=("문서",),
        actions=(),
        keywords=("롯데홈쇼핑", "원산지"),
        required_terms=(),
        preferred_terms=("롯데홈쇼핑", "원산지"),
        confidence=0.3,
        analyzer="fallback",
    )

    outcome = contextual_search(index_path, plan.original_query, analyzer=lambda _: plan)

    assert outcome.results[0].result.file_path == "/고객사/롯데홈쇼핑/원산지확약서.pdf"
    assert all(item.coverage >= 0.5 for item in outcome.results)
