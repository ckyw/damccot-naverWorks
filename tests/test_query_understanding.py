from __future__ import annotations

import json

from src.query_understanding import analyze_with_gemini, fallback_query_plan


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeSession:
    def __init__(self, plan):
        self.plan = plan
        self.request = None

    def post(self, url, **kwargs):
        self.request = {"url": url, **kwargs}
        return _FakeResponse(
            {
                "candidates": [
                    {"content": {"parts": [{"text": json.dumps(self.plan, ensure_ascii=False)}]}}
                ]
            }
        )


def test_gemini_query_analysis_uses_structured_output():
    session = _FakeSession(
        {
            "cleaned_query": "롯데홈쇼핑 원산지 제출 문서",
            "entities": ["롯데홈쇼핑"],
            "topics": ["원산지"],
            "document_types": ["문서"],
            "actions": ["제출"],
            "keywords": ["롯데홈쇼핑", "원산지", "제출"],
            "required_terms": ["롯데홈쇼핑"],
            "preferred_terms": ["원산지", "제출"],
            "confidence": 0.92,
        }
    )

    plan = analyze_with_gemini(
        "롯데홈쇼핑에 제출한 원산지 문서는 어디에?",
        api_key="test-key",
        session=session,
    )

    assert plan.analyzer == "gemini"
    assert plan.entities == ("롯데홈쇼핑",)
    assert plan.required_terms == ("롯데홈쇼핑",)
    assert session.request["headers"]["x-goog-api-key"] == "test-key"
    assert session.request["json"]["generationConfig"]["responseMimeType"] == "application/json"


def test_fallback_removes_question_words_and_particles():
    plan = fallback_query_plan("롯데홈쇼핑에 제출한 원산지 문서는 어디에?")

    assert plan.analyzer == "fallback"
    assert "어디" not in plan.cleaned_query
    assert "롯데홈쇼핑" in plan.keywords
    assert "원산지" in plan.keywords
    assert plan.document_types == ("문서",)
