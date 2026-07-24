from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass
from typing import Any

import requests

from src.search_documents import normalize_search_text


DEFAULT_GEMINI_MODEL = "gemini-3.1-flash-lite"
GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
MAX_QUERY_LENGTH = 500
MAX_TERMS_PER_FIELD = 8

_QUESTION_WORDS = {
    "어디",
    "어디에",
    "어디서",
    "무엇",
    "뭐",
    "어떤",
    "찾아줘",
    "알려줘",
    "있나요",
    "있어",
}
_GENERIC_DOCUMENT_WORDS = {"문서", "자료", "파일", "폴더"}
_PARTICLE_SUFFIXES = ("에게서", "으로", "에서", "에게", "까지", "부터", "처럼", "보다", "에", "의", "을", "를", "은", "는", "이", "가")


@dataclass(frozen=True)
class QueryPlan:
    original_query: str
    cleaned_query: str
    entities: tuple[str, ...]
    topics: tuple[str, ...]
    document_types: tuple[str, ...]
    actions: tuple[str, ...]
    keywords: tuple[str, ...]
    required_terms: tuple[str, ...]
    preferred_terms: tuple[str, ...]
    confidence: float
    analyzer: str

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in (
            "entities",
            "topics",
            "document_types",
            "actions",
            "keywords",
            "required_terms",
            "preferred_terms",
        ):
            payload[key] = list(payload[key])
        return payload


class GeminiQueryError(RuntimeError):
    pass


QUERY_PLAN_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "cleaned_query": {"type": "string"},
        "entities": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
        "topics": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
        "document_types": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
        "actions": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
        "keywords": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
        "required_terms": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
        "preferred_terms": {"type": "array", "items": {"type": "string"}, "maxItems": 8},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": [
        "cleaned_query",
        "entities",
        "topics",
        "document_types",
        "actions",
        "keywords",
        "required_terms",
        "preferred_terms",
        "confidence",
    ],
}

SYSTEM_INSTRUCTION = """You analyze Korean natural-language questions for an internal file search engine.
Return only the requested structured JSON. Remove question phrases and Korean particles.
Extract company, customer, brand, product, department, and project names as entities.
Extract the requested subject as topics and the requested file kind as document_types.
Use required_terms only for explicit entities or constraints that should occur in a file path or name.
Use preferred_terms for topical words. Do not invent file names, paths, companies, or facts.
Keep each search term short and preserve Korean proper nouns."""


def _unique_terms(values: Any) -> tuple[str, ...]:
    if not isinstance(values, list):
        return ()
    terms: list[str] = []
    seen: set[str] = set()
    for value in values[:MAX_TERMS_PER_FIELD]:
        if not isinstance(value, str):
            continue
        term = normalize_search_text(value).strip()
        if not term or len(term) > 80 or term in seen:
            continue
        seen.add(term)
        terms.append(term)
    return tuple(terms)


def _strip_particle(token: str) -> str:
    for suffix in _PARTICLE_SUFFIXES:
        if token.endswith(suffix) and len(token) > len(suffix) + 1:
            return token[: -len(suffix)]
    return token


def fallback_query_plan(query: str) -> QueryPlan:
    original = query.strip()[:MAX_QUERY_LENGTH]
    raw_tokens = re.findall(r"[0-9A-Za-z가-힣]+", original)
    tokens: list[str] = []
    for raw_token in raw_tokens:
        token = _strip_particle(raw_token.lower())
        if token in _QUESTION_WORDS:
            continue
        if token.endswith("한") and len(token) > 2:
            token = token[:-1]
        if token and token not in tokens:
            tokens.append(token)
    document_types = tuple(token for token in tokens if token in _GENERIC_DOCUMENT_WORDS)
    keywords = tuple(token for token in tokens if token not in _GENERIC_DOCUMENT_WORDS)
    return QueryPlan(
        original_query=original,
        cleaned_query=" ".join(keywords or tokens),
        entities=(),
        topics=keywords,
        document_types=document_types,
        actions=tuple(token for token in keywords if token in {"제출", "회신", "검토", "승인"}),
        keywords=keywords,
        required_terms=(),
        preferred_terms=keywords,
        confidence=0.35,
        analyzer="fallback",
    )


def _plan_from_payload(query: str, payload: Any) -> QueryPlan:
    if not isinstance(payload, dict):
        raise GeminiQueryError("Gemini query plan is not a JSON object")
    entities = _unique_terms(payload.get("entities"))
    topics = _unique_terms(payload.get("topics"))
    document_types = _unique_terms(payload.get("document_types"))
    actions = _unique_terms(payload.get("actions"))
    keywords = _unique_terms(payload.get("keywords"))
    required_terms = _unique_terms(payload.get("required_terms"))
    preferred_terms = _unique_terms(payload.get("preferred_terms"))
    if not keywords:
        keywords = tuple(dict.fromkeys((*entities, *topics, *document_types)))
    try:
        confidence = max(0.0, min(float(payload.get("confidence", 0.0)), 1.0))
    except (TypeError, ValueError):
        confidence = 0.0
    cleaned_query = normalize_search_text(str(payload.get("cleaned_query") or " ".join(keywords)))
    if not keywords and not cleaned_query:
        raise GeminiQueryError("Gemini query plan has no searchable terms")
    return QueryPlan(
        original_query=query.strip()[:MAX_QUERY_LENGTH],
        cleaned_query=cleaned_query,
        entities=entities,
        topics=topics,
        document_types=document_types,
        actions=actions,
        keywords=keywords,
        required_terms=required_terms,
        preferred_terms=preferred_terms,
        confidence=confidence,
        analyzer="gemini",
    )


def analyze_with_gemini(
    query: str,
    *,
    api_key: str,
    model: str = DEFAULT_GEMINI_MODEL,
    timeout: float = 10.0,
    session: requests.Session | None = None,
) -> QueryPlan:
    if not api_key.strip():
        raise GeminiQueryError("Gemini API key is empty")
    client = session or requests.Session()
    response = client.post(
        GEMINI_ENDPOINT.format(model=model),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
        json={
            "systemInstruction": {"parts": [{"text": SYSTEM_INSTRUCTION}]},
            "contents": [{"role": "user", "parts": [{"text": query[:MAX_QUERY_LENGTH]}]}],
            "generationConfig": {
                "temperature": 0,
                "responseMimeType": "application/json",
                "responseSchema": QUERY_PLAN_SCHEMA,
            },
        },
        timeout=timeout,
    )
    try:
        response.raise_for_status()
        body = response.json()
        text = body["candidates"][0]["content"]["parts"][0]["text"]
        return _plan_from_payload(query, json.loads(text))
    except (requests.RequestException, KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise GeminiQueryError("Gemini query analysis failed") from exc


def analyze_query(query: str) -> QueryPlan:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return fallback_query_plan(query)
    try:
        return analyze_with_gemini(
            query,
            api_key=api_key,
            model=os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL),
        )
    except GeminiQueryError:
        return fallback_query_plan(query)
