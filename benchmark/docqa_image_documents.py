from __future__ import annotations

import re
from typing import Any

from .schemas import BenchmarkDocument

IMAGE_FORMAT_TYPES = {"bmp", "gif", "jpeg", "jpg", "png", "tif", "tiff", "webp"}


def is_image_only_document(document: BenchmarkDocument) -> bool:
    modality = str(document.modality or "").strip().lower()
    if modality in {"image", "page_image"}:
        return True
    format_type = str(document.format_type or "").strip().lower()
    suffix = document.path.suffix.lower().lstrip(".")
    return (format_type or suffix) in IMAGE_FORMAT_TYPES


def page_image_records_from_documents(
    documents: list[BenchmarkDocument],
) -> list[dict[str, Any]]:
    return [
        page_image_record_from_document(document)
        for document in documents
        if is_image_only_document(document)
    ]


def page_image_record_from_document(document: BenchmarkDocument) -> dict[str, Any]:
    page_label = _document_page_label(document)
    page_number = _page_number_value(page_label)
    image_ref = str(document.path)
    source_backrefs = [f"{document.document_id}#page:{page_label}"]
    return {
        "evidence_id": f"page-image:{document.document_id}:{page_label}",
        "file_id": document.document_id,
        "file_name": document.path.name,
        "page_label": page_label,
        "page_number": page_number,
        "page_image_path": image_ref,
        "rendered_page_image": image_ref,
        "modality": "page_image",
        "text": "",
        "ocr_text": "",
        "source_backrefs": source_backrefs,
        "metadata": {
            "image_ref": image_ref,
            "visual_backend_type": "provided_image",
        },
    }


def _document_page_label(document: BenchmarkDocument) -> str:
    metadata = dict(document.metadata or {})
    for key in ("page_label", "page", "page_number"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    for value in (document.document_id, document.path.stem):
        match = re.search(r"(?:^|[_-])page[_-]?(\d+)(?:$|[_-])", str(value))
        if match:
            return match.group(1)
    return "1"


def _page_number_value(page_label: str) -> int | None:
    try:
        return int(str(page_label).strip())
    except ValueError:
        return None
