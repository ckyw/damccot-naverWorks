from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from src.batcher import IMAGE_EXTENSIONS
from src.utils import write_text


PRODUCT_KEYWORDS = ["팥죽", "양갱", "생강차", "팥밀크", "파덱밀크", "빙수", "떡", "선물세트"]
DOCUMENT_EXTENSIONS = {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "hwp", "hwpx"}
REVIEW_WORDS = ["최종", "진짜최종", "수정", "구버전", "old", "2025"]
REGULATORY_WORDS = ["인증", "인증서", "품질", "위생", "haccp", "시험성적서", "품목제조보고서"]


def write_reports(items: list[dict[str, Any]], output_dir: Path) -> None:
    reports_dir = output_dir / "reports"
    write_text(reports_dir / "top_level_folders.md", top_level_folders_report(items))
    write_text(reports_dir / "folder_statistics.md", folder_statistics_report(items))
    write_text(reports_dir / "file_type_distribution.md", file_type_distribution_report(items))
    write_text(reports_dir / "product_keyword_candidates.md", product_keyword_candidates_report(items))
    write_text(reports_dir / "review_needed_folders.md", review_needed_folders_report(items))


def top_level_folders_report(items: list[dict[str, Any]]) -> str:
    top_folders = sorted(
        [item for item in items if item.get("depth") == 1 and item.get("isFolder")],
        key=lambda item: str(item.get("fileName") or ""),
    )
    child_counts = Counter(item.get("parentFileId") for item in items)
    lines = ["# Top-level Folders", "", "| Folder | Path | Direct children |", "|---|---|---:|"]
    for item in top_folders:
        lines.append(
            f"| {item.get('fileName') or ''} | {item.get('filePath') or ''} | "
            f"{child_counts.get(item.get('fileId'), 0)} |"
        )
    return "\n".join(lines) + "\n"


def folder_statistics_report(items: list[dict[str, Any]]) -> str:
    major_folders = [
        item for item in items if item.get("depth") == 1 and item.get("isFolder") and item.get("filePath")
    ]
    lines = [
        "# Folder Statistics",
        "",
        "| Major folder | Total descendants | Folders | Files | Images | Documents | Latest modified |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for folder in sorted(major_folders, key=lambda item: str(item.get("fileName") or "")):
        prefix = str(folder.get("filePath") or "").rstrip("/") + "/"
        descendants = [item for item in items if str(item.get("filePath") or "").startswith(prefix)]
        folders = sum(1 for item in descendants if item.get("isFolder"))
        files = len(descendants) - folders
        images = sum(1 for item in descendants if item.get("extension") in IMAGE_EXTENSIONS)
        docs = sum(1 for item in descendants if item.get("extension") in DOCUMENT_EXTENSIONS)
        latest = max((str(item.get("modifiedTime") or "") for item in descendants), default="")
        lines.append(
            f"| {folder.get('fileName') or ''} | {len(descendants)} | {folders} | {files} | "
            f"{images} | {docs} | {latest} |"
        )
    return "\n".join(lines) + "\n"


def file_type_distribution_report(items: list[dict[str, Any]]) -> str:
    by_type = Counter(str(item.get("fileType") or "unknown") for item in items)
    by_extension = Counter(str(item.get("extension") or "(none)") for item in items)
    lines = ["# File Type Distribution", "", "## By fileType", "", "| fileType | Count |", "|---|---:|"]
    for file_type, count in by_type.most_common():
        lines.append(f"| {file_type} | {count} |")
    lines.extend(["", "## By extension", "", "| Extension | Count |", "|---|---:|"])
    for extension, count in by_extension.most_common():
        lines.append(f"| {extension} | {count} |")
    return "\n".join(lines) + "\n"


def product_keyword_candidates_report(items: list[dict[str, Any]]) -> str:
    lines = ["# Product Keyword Candidates", ""]
    for keyword in PRODUCT_KEYWORDS:
        matches = [
            item
            for item in items
            if keyword in str(item.get("filePath") or "") or keyword in str(item.get("fileName") or "")
        ]
        folders = Counter(_major_folder_name(item) for item in matches)
        lines.extend(
            [
                f"## {keyword}",
                "",
                f"- Matched paths: {len(matches)}",
                f"- Common folders: {', '.join(name for name, _ in folders.most_common(5)) or '(none)'}",
                "- Representative paths:",
            ]
        )
        for item in matches[:10]:
            lines.append(f"  - {item.get('filePath') or item.get('fileName') or ''}")
        lines.append("")
    return "\n".join(lines)


def review_needed_folders_report(items: list[dict[str, Any]]) -> str:
    by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    folders_by_id = {
        str(item.get("fileId")): item for item in items if item.get("isFolder") and item.get("fileId")
    }
    for item in items:
        parent_id = item.get("parentFileId")
        if parent_id:
            by_parent[str(parent_id)].append(item)

    lines = ["# Review Needed Folders", "", "| Folder | Reasons |", "|---|---|"]
    found = False
    for folder_id, children in by_parent.items():
        folder = folders_by_id.get(folder_id)
        if not folder:
            continue
        reasons = _review_reasons(folder, children)
        if reasons:
            found = True
            lines.append(f"| {folder.get('filePath') or folder.get('fileName') or folder_id} | {', '.join(reasons)} |")
    if not found:
        lines.append("| (none) | No folder matched the initial review heuristics. |")
    return "\n".join(lines) + "\n"


def _major_folder_name(item: dict[str, Any]) -> str:
    path = str(item.get("filePath") or "")
    parts = [part for part in path.split("/") if part]
    return parts[0] if parts else "(unknown)"


def _review_reasons(folder: dict[str, Any], children: list[dict[str, Any]]) -> list[str]:
    reasons: list[str] = []
    folder_text = f"{folder.get('fileName') or ''} {folder.get('filePath') or ''}".lower()
    if any(word.lower() in folder_text for word in REVIEW_WORDS):
        reasons.append("review keyword in folder name/path")

    image_files = [item for item in children if item.get("extension") in IMAGE_EXTENSIONS]
    numeric_images = [
        item
        for item in image_files
        if re.search(r"(^|[/_\-\s])(img|dsc|photo)?_?\d{3,}", str(item.get("fileName") or ""), re.I)
    ]
    if len(numeric_images) >= 10:
        reasons.append("many numeric image filenames")

    if len(children) >= 50 and len(str(folder.get("fileName") or "")) <= 3:
        reasons.append("many files with weak semantic folder naming")

    if any(item.get("hasPermission") is False for item in children):
        reasons.append("permission-limited child items")

    if any(word in folder_text for word in REGULATORY_WORDS):
        old_items = [item for item in children if _is_before_year(item.get("modifiedTime"), 2023)]
        if old_items:
            reasons.append("old regulatory/certificate related files")

    return reasons


def _is_before_year(value: Any, year: int) -> bool:
    if not value:
        return False
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.year < year
