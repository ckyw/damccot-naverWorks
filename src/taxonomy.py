from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from src.search_documents import SearchDocument, normalize_search_text, search_text_contains


@dataclass(frozen=True)
class TaxonomyRule:
    category: str
    tag: str
    terms: tuple[str, ...]
    extensions: tuple[str, ...]
    file_types: tuple[str, ...]


@dataclass(frozen=True)
class TaxonomyConfig:
    version: str
    rules: tuple[TaxonomyRule, ...]


@dataclass(frozen=True)
class SynonymGroup:
    canonical: str
    terms: tuple[str, ...]


@dataclass(frozen=True)
class SynonymConfig:
    version: str
    groups: tuple[SynonymGroup, ...]


def _read_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a mapping in {path}")
    return payload


def load_taxonomy(path: Path) -> TaxonomyConfig:
    payload = _read_yaml(path)
    rules: list[TaxonomyRule] = []
    categories = payload.get("categories") or {}
    if not isinstance(categories, dict):
        raise ValueError("taxonomy categories must be a mapping")
    for category, entries in categories.items():
        for entry in entries or []:
            rules.append(
                TaxonomyRule(
                    category=str(category),
                    tag=str(entry["tag"]),
                    terms=tuple(normalize_search_text(value) for value in entry.get("terms", [])),
                    extensions=tuple(str(value).lower().lstrip(".") for value in entry.get("extensions", [])),
                    file_types=tuple(str(value).lower() for value in entry.get("file_types", [])),
                )
            )
    return TaxonomyConfig(version=str(payload.get("version") or "unknown"), rules=tuple(rules))


def load_synonyms(path: Path) -> SynonymConfig:
    payload = _read_yaml(path)
    groups = tuple(
        SynonymGroup(
            canonical=str(entry["canonical"]),
            terms=tuple(normalize_search_text(value) for value in entry.get("terms", [])),
        )
        for entry in payload.get("groups", [])
    )
    return SynonymConfig(version=str(payload.get("version") or "unknown"), groups=groups)


def tags_for(document: SearchDocument, taxonomy: TaxonomyConfig) -> tuple[tuple[str, str], ...]:
    matches: set[tuple[str, str]] = set()
    for rule in taxonomy.rules:
        matched = (
            any(search_text_contains(document.searchable_text, term) for term in rule.terms)
            or document.extension in rule.extensions
            or document.file_type in rule.file_types
        )
        if matched:
            matches.add((rule.category, rule.tag))
    return tuple(sorted(matches))
def aliases_for(document: SearchDocument, synonyms: SynonymConfig) -> tuple[str, ...]:
    aliases: set[str] = set()
    for group in synonyms.groups:
        if any(search_text_contains(document.searchable_text, term) for term in group.terms):
            aliases.add(normalize_search_text(group.canonical))
            aliases.update(group.terms)
    return tuple(sorted(alias for alias in aliases if alias))
