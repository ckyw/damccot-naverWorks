from __future__ import annotations

import json
import os
import shlex
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.search_documents import (
    SearchDocument,
    document_from_item,
    normalize_search_text,
    search_text_contains,
)
from src.sensitive_filter import is_sensitive_path
from src.search_sources import SearchSource
from src.taxonomy import (
    aliases_for,
    load_synonyms,
    load_taxonomy,
    tags_for,
)


SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class BuildStats:
    total_items: int
    indexed_items: int
    sensitive_excluded: int
    invalid_excluded: int
    duplicate_excluded: int
    untagged_items: int


@dataclass(frozen=True)
class SearchResult:
    file_name: str
    file_path: str
    file_type: str
    extension: str
    is_folder: bool
    modified_time: str
    tags: tuple[str, ...]
    score: float

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["tags"] = list(self.tags)
        return payload


@dataclass(frozen=True)
class ParsedQuery:
    text: str
    file_type: str
    extension: str
    tag: str


@dataclass(frozen=True)
class IndexValidation:
    integrity_check: str
    document_count: int
    fts_count: int
    metadata_indexed_items: int
    sensitive_path_count: int
    valid: bool


def _connect(path: Path, *, read_only: bool = False) -> sqlite3.Connection:
    if read_only:
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    else:
        connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def _create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        PRAGMA foreign_keys = ON;
        CREATE TABLE index_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );
        CREATE TABLE documents (
            id INTEGER PRIMARY KEY,
            document_key TEXT NOT NULL UNIQUE,
            source_drive_id TEXT NOT NULL,
            source_drive_name TEXT NOT NULL,
            file_id TEXT NOT NULL,
            parent_file_id TEXT NOT NULL,
            file_name TEXT NOT NULL,
            normalized_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            normalized_path TEXT NOT NULL,
            file_type TEXT NOT NULL,
            extension TEXT NOT NULL,
            is_folder INTEGER NOT NULL,
            modified_time TEXT NOT NULL,
            aliases_text TEXT NOT NULL,
            tags_text TEXT NOT NULL
        );
        CREATE TABLE tags (
            id INTEGER PRIMARY KEY,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            UNIQUE(category, name)
        );
        CREATE TABLE document_tags (
            document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            tag_id INTEGER NOT NULL REFERENCES tags(id) ON DELETE CASCADE,
            rule_source TEXT NOT NULL,
            PRIMARY KEY(document_id, tag_id)
        );
        CREATE TABLE synonyms (
            canonical TEXT NOT NULL,
            term TEXT NOT NULL,
            PRIMARY KEY(canonical, term)
        );
        CREATE VIRTUAL TABLE documents_fts USING fts5(
            document_id UNINDEXED,
            file_name,
            normalized_name,
            file_path,
            normalized_path,
            aliases,
            tags,
            tokenize = 'unicode61 remove_diacritics 2'
        );
        CREATE INDEX documents_file_type_idx ON documents(file_type);
        CREATE INDEX documents_extension_idx ON documents(extension);
        CREATE INDEX document_tags_tag_idx ON document_tags(tag_id);
        """
    )


def _insert_document(
    connection: sqlite3.Connection,
    document: SearchDocument,
    *,
    tags: tuple[tuple[str, str], ...],
    aliases: tuple[str, ...],
    taxonomy_version: str,
) -> None:
    tags_text = " ".join(tag for _, tag in tags)
    aliases_text = " ".join(aliases)
    cursor = connection.execute(
        """
        INSERT INTO documents (
            document_key, source_drive_id, source_drive_name, file_id,
            parent_file_id, file_name, normalized_name, file_path,
            normalized_path, file_type, extension, is_folder, modified_time,
            aliases_text, tags_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            document.document_key,
            document.source_drive_id,
            document.source_drive_name,
            document.file_id,
            document.parent_file_id,
            document.file_name,
            document.normalized_name,
            document.file_path,
            document.normalized_path,
            document.file_type,
            document.extension,
            int(document.is_folder),
            document.modified_time,
            aliases_text,
            tags_text,
        ),
    )
    document_id = int(cursor.lastrowid)
    for category, tag in tags:
        connection.execute(
            "INSERT OR IGNORE INTO tags (category, name) VALUES (?, ?)",
            (category, tag),
        )
        tag_id = connection.execute(
            "SELECT id FROM tags WHERE category = ? AND name = ?",
            (category, tag),
        ).fetchone()["id"]
        connection.execute(
            "INSERT INTO document_tags (document_id, tag_id, rule_source) VALUES (?, ?, ?)",
            (document_id, tag_id, f"taxonomy:{taxonomy_version}"),
        )
    connection.execute(
        """
        INSERT INTO documents_fts (
            document_id, file_name, normalized_name, file_path,
            normalized_path, aliases, tags
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            document_id,
            document.file_name,
            document.normalized_name,
            document.file_path,
            document.normalized_path,
            aliases_text,
            tags_text,
        ),
    )


def build_search_index(
    input_path: Path,
    output_path: Path,
    *,
    taxonomy_path: Path,
    synonyms_path: Path,
) -> BuildStats:
    return build_search_index_from_sources(
        (SearchSource(name=input_path.parent.parent.name or "default", path=input_path),),
        output_path,
        taxonomy_path=taxonomy_path,
        synonyms_path=synonyms_path,
    )


def build_search_index_from_sources(
    sources: tuple[SearchSource, ...],
    output_path: Path,
    *,
    taxonomy_path: Path,
    synonyms_path: Path,
) -> BuildStats:
    if not sources:
        raise ValueError("At least one search source is required")

    taxonomy = load_taxonomy(taxonomy_path)
    synonyms = load_synonyms(synonyms_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")
    temporary_path.unlink(missing_ok=True)

    counts = {
        "sensitive_excluded": 0,
        "invalid_excluded": 0,
        "duplicate_excluded": 0,
        "untagged_items": 0,
    }
    seen_keys: set[str] = set()
    total_items = 0
    source_summaries: list[dict[str, Any]] = []
    connection = _connect(temporary_path)
    try:
        _create_schema(connection)
        for group in synonyms.groups:
            for term in group.terms:
                connection.execute(
                    "INSERT OR IGNORE INTO synonyms (canonical, term) VALUES (?, ?)",
                    (normalize_search_text(group.canonical), term),
                )

        for source in sources:
            payload = json.loads(source.path.read_text(encoding="utf-8"))
            items = payload.get("items")
            if not isinstance(items, list):
                raise ValueError(f"Raw tree JSON must contain an items list: {source.path}")
            source_drive_id = str(payload.get("sharedriveId") or source.name)
            total_items += len(items)
            source_summaries.append(
                {
                    "name": source.name,
                    "path": str(source.path),
                    "sharedrive_id": source_drive_id,
                    "collected_at": str(payload.get("collectedAt") or ""),
                    "total_items": len(items),
                }
            )
            for item in items:
                if not isinstance(item, dict):
                    counts["invalid_excluded"] += 1
                    continue
                path = str(item.get("filePath") or "")
                if path and is_sensitive_path(path):
                    counts["sensitive_excluded"] += 1
                    continue
                document = document_from_item(
                    item,
                    source_drive_id=source_drive_id,
                    source_drive_name=source.name,
                )
                if document is None:
                    counts["invalid_excluded"] += 1
                    continue
                if document.document_key in seen_keys:
                    counts["duplicate_excluded"] += 1
                    continue
                seen_keys.add(document.document_key)
                tags = tags_for(document, taxonomy)
                aliases = aliases_for(document, synonyms)
                if not tags:
                    counts["untagged_items"] += 1
                _insert_document(
                    connection,
                    document,
                    tags=tags,
                    aliases=aliases,
                    taxonomy_version=taxonomy.version,
                )

        indexed_items = len(seen_keys)
        stats = BuildStats(
            total_items=total_items,
            indexed_items=indexed_items,
            sensitive_excluded=counts["sensitive_excluded"],
            invalid_excluded=counts["invalid_excluded"],
            duplicate_excluded=counts["duplicate_excluded"],
            untagged_items=counts["untagged_items"],
        )
        metadata = {
            "schema_version": SCHEMA_VERSION,
            "source_count": str(len(sources)),
            "sources": json.dumps(source_summaries, ensure_ascii=False, sort_keys=True),
            "taxonomy_version": taxonomy.version,
            "synonyms_version": synonyms.version,
            **{key: str(value) for key, value in asdict(stats).items()},
        }
        connection.executemany(
            "INSERT INTO index_metadata (key, value) VALUES (?, ?)",
            sorted(metadata.items()),
        )
        connection.execute("INSERT INTO documents_fts(documents_fts) VALUES('optimize')")
        connection.commit()
    except Exception:
        connection.close()
        temporary_path.unlink(missing_ok=True)
        raise
    else:
        connection.close()
        os.replace(temporary_path, output_path)
        return stats


def parse_query(query: str) -> ParsedQuery:
    filters = {"type": "", "ext": "", "tag": ""}
    terms: list[str] = []
    try:
        tokens = shlex.split(query)
    except ValueError:
        tokens = query.split()
    for token in tokens:
        key, separator, value = token.partition(":")
        if separator and key.lower() in filters and value:
            filters[key.lower()] = normalize_search_text(value)
        else:
            terms.append(token)
    return ParsedQuery(
        text=normalize_search_text(" ".join(terms)),
        file_type=filters["type"],
        extension=filters["ext"].lstrip("."),
        tag=filters["tag"],
    )


def _expanded_terms(connection: sqlite3.Connection, text: str) -> tuple[str, ...]:
    original_terms = {term for term in text.split() if term}
    terms = set(original_terms)
    synonym_rows = connection.execute("SELECT canonical, term FROM synonyms").fetchall()
    grouped: dict[str, set[str]] = {}
    for row in synonym_rows:
        canonical = str(row["canonical"])
        synonym = str(row["term"])
        grouped.setdefault(canonical, set()).add(synonym)
    for canonical, synonyms in grouped.items():
        if (
            canonical in original_terms
            or canonical in text
            or any(synonym in original_terms or synonym in text for synonym in synonyms)
        ):
            terms.add(canonical)
            for synonym in synonyms:
                terms.update(part for part in synonym.split() if part)
    return tuple(sorted(terms))


def _supports_substring_match(term: str) -> bool:
    return any("가" <= character <= "힣" for character in term) or len(term) >= 4


def _contains_term(value: str, term: str) -> bool:
    return search_text_contains(value, term)


def _filter_sql(parsed: ParsedQuery, *, alias: str = "d") -> tuple[str, list[str]]:
    clauses: list[str] = []
    values: list[str] = []
    if parsed.file_type:
        clauses.append(f"{alias}.file_type = ?")
        values.append(parsed.file_type)
    if parsed.extension:
        clauses.append(f"{alias}.extension = ?")
        values.append(parsed.extension)
    if parsed.tag:
        clauses.append(f"{alias}.tags_text LIKE ?")
        values.append(f"%{parsed.tag}%")
    return (" AND ".join(clauses) if clauses else "1 = 1"), values


def _fts_expression(terms: tuple[str, ...]) -> str:
    safe_terms = [f'"{term.replace(chr(34), chr(34) * 2)}"' for term in terms if term]
    return " OR ".join(safe_terms)


def _candidate_rows(
    connection: sqlite3.Connection,
    parsed: ParsedQuery,
    terms: tuple[str, ...],
) -> dict[int, tuple[sqlite3.Row, bool]]:
    filter_sql, filter_values = _filter_sql(parsed)
    candidates: dict[int, tuple[sqlite3.Row, bool]] = {}
    fts_expression = _fts_expression(terms)
    if fts_expression:
        rows = connection.execute(
            f"""
            SELECT d.*
            FROM documents_fts f
            JOIN documents d ON d.id = f.document_id
            WHERE documents_fts MATCH ? AND {filter_sql}
            """,
            [fts_expression, *filter_values],
        ).fetchall()
        candidates.update({int(row["id"]): (row, True) for row in rows})

    if terms:
        like_clauses: list[str] = []
        like_values: list[str] = []
        for term in (term for term in terms if _supports_substring_match(term)):
            like_clauses.append(
                "(d.normalized_name LIKE ? OR d.normalized_path LIKE ? "
                "OR d.aliases_text LIKE ? OR d.tags_text LIKE ?)"
            )
            like_values.extend([f"%{term}%"] * 4)
        if like_clauses:
            rows = connection.execute(
                f"""
                SELECT d.* FROM documents d
                WHERE {filter_sql} AND ({' OR '.join(like_clauses)})
                """,
                [*filter_values, *like_values],
            ).fetchall()
            for row in rows:
                document_id = int(row["id"])
                previous = candidates.get(document_id)
                candidates[document_id] = (row, bool(previous and previous[1]))
    elif filter_sql != "1 = 1":
        rows = connection.execute(
            f"SELECT d.* FROM documents d WHERE {filter_sql}", filter_values
        ).fetchall()
        candidates.update({int(row["id"]): (row, False) for row in rows})
    return candidates


def _score(row: sqlite3.Row, parsed: ParsedQuery, terms: tuple[str, ...], fts_match: bool) -> float:
    name = str(row["normalized_name"])
    path = str(row["normalized_path"])
    aliases = str(row["aliases_text"])
    tags = str(row["tags_text"])
    score = 5.0 if fts_match else 0.0
    if parsed.text and name == parsed.text:
        score += 100.0
    elif parsed.text and parsed.text in name:
        score += 40.0
    for term in terms:
        if _contains_term(name, term):
            score += 20.0
        if _contains_term(path, term):
            score += 6.0
        if _contains_term(tags, term):
            score += 10.0
        if _contains_term(aliases, term):
            score += 8.0
    if parsed.file_type or parsed.extension or parsed.tag:
        score += 3.0
    return score


def search_index(index_path: Path, query: str, *, limit: int = 20) -> list[SearchResult]:
    if not index_path.exists():
        raise FileNotFoundError(index_path)
    parsed = parse_query(query)
    if not parsed.text and not (parsed.file_type or parsed.extension or parsed.tag):
        return []
    with _connect(index_path, read_only=True) as connection:
        terms = _expanded_terms(connection, parsed.text)
        candidates = _candidate_rows(connection, parsed, terms)
        scored = [
            (_score(row, parsed, terms, fts_match), row)
            for row, fts_match in candidates.values()
        ]
        scored.sort(key=lambda pair: str(pair[1]["file_name"]))
        scored.sort(key=lambda pair: str(pair[1]["modified_time"]), reverse=True)
        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [
            SearchResult(
                file_name=str(row["file_name"]),
                file_path=str(row["file_path"]),
                file_type=str(row["file_type"]),
                extension=str(row["extension"]),
                is_folder=bool(row["is_folder"]),
                modified_time=str(row["modified_time"]),
                tags=tuple(tag for tag in str(row["tags_text"]).split() if tag),
                score=score,
            )
            for score, row in scored[: max(1, min(limit, 100))]
        ]


def index_metadata(index_path: Path) -> dict[str, str]:
    with _connect(index_path, read_only=True) as connection:
        return {
            str(row["key"]): str(row["value"])
            for row in connection.execute("SELECT key, value FROM index_metadata ORDER BY key")
        }


def validate_index(index_path: Path) -> IndexValidation:
    with _connect(index_path, read_only=True) as connection:
        integrity_check = str(connection.execute("PRAGMA integrity_check").fetchone()[0])
        document_count = int(connection.execute("SELECT COUNT(*) FROM documents").fetchone()[0])
        fts_count = int(connection.execute("SELECT COUNT(*) FROM documents_fts").fetchone()[0])
        metadata_row = connection.execute(
            "SELECT value FROM index_metadata WHERE key = 'indexed_items'"
        ).fetchone()
        metadata_indexed_items = int(metadata_row["value"]) if metadata_row else -1
        sensitive_path_count = sum(
            1
            for row in connection.execute("SELECT file_path FROM documents")
            if is_sensitive_path(str(row["file_path"]))
        )
    valid = (
        integrity_check == "ok"
        and document_count == fts_count == metadata_indexed_items
        and sensitive_path_count == 0
    )
    return IndexValidation(
        integrity_check=integrity_check,
        document_count=document_count,
        fts_count=fts_count,
        metadata_indexed_items=metadata_indexed_items,
        sensitive_path_count=sensitive_path_count,
        valid=valid,
    )
