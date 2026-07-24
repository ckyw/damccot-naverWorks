from __future__ import annotations

from pathlib import Path
from typing import Any

from src.utils import write_json


PRODUCT_ASSET_KEYWORDS = ["제품", "상품", "상세페이지", "패키지", "이미지"]
DESIGN_KEYWORDS = ["디자인", "패키지", "ai", "psd", "시안"]
QUALITY_KEYWORDS = ["품질", "위생", "인증서", "HACCP", "품목제조보고서", "시험성적서"]
IMAGE_KEYWORDS = ["이미지", "촬영", "사진", "폰촬영", "핸드폰"]
IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp", "heic", "tif", "tiff", "bmp"}


def _haystack(item: dict[str, Any]) -> str:
    return f"{item.get('filePath') or ''} {item.get('fileName') or ''}".lower()


def _matches(item: dict[str, Any], keywords: list[str]) -> bool:
    haystack = _haystack(item)
    return any(keyword.lower() in haystack for keyword in keywords)


def gemini_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "fileName": item.get("fileName"),
        "filePath": item.get("filePath"),
        "fileType": item.get("fileType"),
        "extension": item.get("extension"),
        "modifiedTime": item.get("modifiedTime"),
        "depth": item.get("depth"),
    }


def build_batches(items: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    top_level = [item for item in items if item.get("depth") == 1]
    product_assets = [item for item in items if _matches(item, PRODUCT_ASSET_KEYWORDS)]
    design = [item for item in items if _matches(item, DESIGN_KEYWORDS)]
    quality_docs = [item for item in items if _matches(item, QUALITY_KEYWORDS)]
    images = [
        item
        for item in items
        if item.get("extension") in IMAGE_EXTENSIONS or _matches(item, IMAGE_KEYWORDS)
    ]

    return {
        "batch_001_top_level.json": [gemini_item(item) for item in top_level],
        "batch_002_product_assets.json": [gemini_item(item) for item in product_assets],
        "batch_003_design.json": [gemini_item(item) for item in design],
        "batch_004_quality_docs.json": [gemini_item(item) for item in quality_docs],
        "batch_005_images.json": [gemini_item(item) for item in images],
    }


def write_batches(items: list[dict[str, Any]], output_dir: Path) -> None:
    for filename, batch_items in build_batches(items).items():
        write_json(output_dir / "batches" / filename, {"totalItems": len(batch_items), "items": batch_items})

