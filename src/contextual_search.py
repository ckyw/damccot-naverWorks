from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from src.query_understanding import QueryPlan, analyze_query
from src.search_documents import normalize_search_text, search_text_contains
from src.search_index import SearchResult, search_index


@dataclass(frozen=True)
class RankedResult:
    result: SearchResult
    score: float
    coverage: float
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "fileName": self.result.file_name,
            "filePath": self.result.file_path,
            "fileType": self.result.file_type,
            "extension": self.result.extension,
            "isFolder": self.result.is_folder,
            "modifiedTime": self.result.modified_time,
            "tags": list(self.result.tags),
            "score": round(self.score, 2),
            "coverage": round(self.coverage, 3),
            "reasons": list(self.reasons),
        }
        return payload


@dataclass(frozen=True)
class ResultGroup:
    folder_path: str
    score: float
    results: tuple[RankedResult, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "folderPath": self.folder_path,
            "score": round(self.score, 2),
            "matchCount": len(self.results),
            "results": [result.as_dict() for result in self.results],
        }


@dataclass(frozen=True)
class ContextualSearchOutcome:
    plan: QueryPlan
    results: tuple[RankedResult, ...]
    groups: tuple[ResultGroup, ...]
    required_terms_relaxed: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "query": self.plan.original_query,
            "analysis": self.plan.as_dict(),
            "requiredTermsRelaxed": self.required_terms_relaxed,
            "total": len(self.results),
            "results": [result.as_dict() for result in self.results],
            "groups": [group.as_dict() for group in self.groups],
        }


def _matches(text: str, term: str) -> bool:
    return search_text_contains(text, normalize_search_text(term))


def _candidate_results(index_path: Path, plan: QueryPlan) -> dict[str, SearchResult]:
    terms = tuple(
        dict.fromkeys(
            term
            for term in (
                *plan.required_terms,
                *plan.entities,
                *plan.topics,
                *plan.preferred_terms,
                *plan.keywords,
            )
            if term
        )
    )
    candidates: dict[str, SearchResult] = {}
    for term in terms[:12]:
        for result in search_index(index_path, term, limit=100):
            previous = candidates.get(result.file_path)
            if previous is None or result.score > previous.score:
                candidates[result.file_path] = result
    if len(terms) > 1:
        for result in search_index(index_path, " ".join(terms), limit=100):
            previous = candidates.get(result.file_path)
            if previous is None or result.score > previous.score:
                candidates[result.file_path] = result
    return candidates


def _rank(result: SearchResult, plan: QueryPlan) -> RankedResult:
    normalized_name = normalize_search_text(result.file_name)
    normalized_path = normalize_search_text(result.file_path)
    normalized_tags = normalize_search_text(" ".join(result.tags))
    searchable = " ".join((normalized_name, normalized_path, normalized_tags))
    scoring_terms = tuple(dict.fromkeys((*plan.keywords, *plan.required_terms, *plan.preferred_terms)))
    matched_terms = tuple(term for term in scoring_terms if _matches(searchable, term))
    coverage = len(matched_terms) / len(scoring_terms) if scoring_terms else 0.0
    score = result.score + coverage * 140.0
    reasons: list[str] = []

    required_matches = sum(_matches(searchable, term) for term in plan.required_terms)
    if required_matches:
        score += required_matches * 70.0
        reasons.append("필수 검색어 일치")
    for entity in plan.entities:
        if _matches(normalized_name, entity):
            score += 45.0
            reasons.append(f"파일명 개체 일치: {entity}")
        elif _matches(normalized_path, entity):
            score += 55.0
            reasons.append(f"경로 개체 일치: {entity}")
    for topic in plan.topics:
        if _matches(normalized_name, topic):
            score += 35.0
            reasons.append(f"파일명 주제 일치: {topic}")
        elif _matches(normalized_path, topic):
            score += 18.0
            reasons.append(f"경로 주제 일치: {topic}")
    if "문서" in plan.document_types and not result.is_folder:
        score += 15.0
        reasons.append("문서 유형 일치")
    if coverage == 1.0 and scoring_terms:
        score += 40.0
        reasons.append("모든 검색어 충족")
    elif coverage >= 0.5:
        reasons.append("주요 검색어 충족")
    return RankedResult(result=result, score=score, coverage=coverage, reasons=tuple(dict.fromkeys(reasons)))


def _group_path(result: SearchResult, plan: QueryPlan) -> str:
    path = PurePosixPath(result.file_path.rstrip("/"))
    parts = path.parts
    entity_index = -1
    for index, part in enumerate(parts):
        if any(_matches(normalize_search_text(part), entity) for entity in plan.entities):
            entity_index = index
    if entity_index >= 0:
        return str(PurePosixPath(*parts[: entity_index + 1])) + "/"
    if result.is_folder:
        return str(path) + "/"
    return str(path.parent) + "/"


def _group_results(ranked: tuple[RankedResult, ...], plan: QueryPlan) -> tuple[ResultGroup, ...]:
    grouped: dict[str, list[RankedResult]] = {}
    for item in ranked:
        grouped.setdefault(_group_path(item.result, plan), []).append(item)
    groups = [
        ResultGroup(folder_path=folder, score=max(item.score for item in items), results=tuple(items[:5]))
        for folder, items in grouped.items()
    ]
    groups.sort(key=lambda group: (-group.score, group.folder_path))
    return tuple(groups[:10])


def contextual_search(
    index_path: Path,
    query: str,
    *,
    limit: int = 20,
    analyzer: Callable[[str], QueryPlan] = analyze_query,
) -> ContextualSearchOutcome:
    plan = analyzer(query)
    candidates = _candidate_results(index_path, plan)
    ranked = tuple(sorted((_rank(result, plan) for result in candidates.values()), key=lambda item: (-item.score, item.result.file_path)))

    strict = tuple(
        item
        for item in ranked
        if all(
            _matches(
                " ".join((normalize_search_text(item.result.file_name), normalize_search_text(item.result.file_path))),
                term,
            )
            for term in plan.required_terms
        )
    )
    required_terms_relaxed = bool(plan.required_terms and not strict)
    selected = strict if strict else ranked
    scoring_terms = tuple(dict.fromkeys((*plan.keywords, *plan.required_terms, *plan.preferred_terms)))
    if not plan.required_terms and len(scoring_terms) > 1 and selected:
        best_coverage = max(item.coverage for item in selected)
        minimum_coverage = min(0.5, best_coverage)
        selected = tuple(item for item in selected if item.coverage >= minimum_coverage)
    selected = selected[: max(1, min(limit, 50))]
    return ContextualSearchOutcome(
        plan=plan,
        results=selected,
        groups=_group_results(selected, plan),
        required_terms_relaxed=required_terms_relaxed,
    )
