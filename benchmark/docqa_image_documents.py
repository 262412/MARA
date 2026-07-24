from __future__ import annotations

import re
from typing import Any

from .schemas import BenchmarkDocument

IMAGE_FORMAT_TYPES = {"bmp", "gif", "jpeg", "jpg", "png", "tif", "tiff", "webp"}
ELEMENT_RECORD_KEYS = (
    "element_index_records",
    "element_index",
    "layout_elements",
    "elements",
)


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


def element_index_records_from_documents(
    documents: list[BenchmarkDocument],
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for document in documents:
        records.extend(_offline_element_records(document))
        for payload in _document_element_payloads(document):
            record = _element_index_record_from_payload(
                document, payload, len(records) + 1
            )
            if record is not None:
                records.append(record)
    return _unique_element_records(records)


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


def _document_element_payloads(document: BenchmarkDocument) -> list[dict[str, Any]]:
    metadata = dict(document.metadata or {})
    payloads: list[dict[str, Any]] = []
    for key in ELEMENT_RECORD_KEYS:
        value = metadata.get(key)
        if isinstance(value, list):
            payloads.extend(item for item in value if isinstance(item, dict))
    return payloads


def _offline_element_records(document: BenchmarkDocument) -> list[dict[str, Any]]:
    from ktem.docqa.offline_layout_index import offline_element_records_for_file

    return offline_element_records_for_file(
        file_id=document.document_id,
        file_name=document.path.name,
        file_path=document.path,
    )


def _element_index_record_from_payload(
    document: BenchmarkDocument,
    payload: dict[str, Any],
    index: int,
) -> dict[str, Any] | None:
    page_label = str(
        payload.get("page_label")
        or payload.get("page")
        or _document_page_label(document)
    ).strip()
    file_id = str(
        payload.get("file_id") or payload.get("source_id") or document.document_id
    ).strip()
    if not page_label or not file_id:
        return None

    element_id = str(
        payload.get("element_id") or payload.get("id") or f"element-{index}"
    ).strip()
    text = str(payload.get("text") or payload.get("ocr_text") or "").strip()
    caption = str(payload.get("caption") or "").strip()
    if not element_id or (not text and not caption and payload.get("bbox") is None):
        return None

    file_name = str(
        payload.get("file_name") or payload.get("source_name") or document.path.name
    ).strip()
    raw_metadata = payload.get("metadata")
    metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
    output = {
        "evidence_id": str(
            payload.get("evidence_id") or f"element:{file_id}:{page_label}:{element_id}"
        ),
        "file_id": file_id,
        "file_name": file_name,
        "page_label": page_label,
        "element_id": element_id,
        "modality": str(
            payload.get("modality") or payload.get("element_type") or "element"
        ),
        "bbox": payload.get("bbox"),
        "caption": caption,
        "text": text,
        "source_backrefs": _source_backrefs(payload, file_id, page_label),
        "metadata": dict(metadata),
    }
    for field in (
        "parent_element_id",
        "section_id",
        "table_id",
        "continuation_id",
        "normalized_text_hash",
    ):
        value = str(payload.get(field) or metadata.get(field) or "").strip()
        if value:
            output[field] = value
    for field in ("row_index", "column_index", "chunk_start", "chunk_end"):
        value = payload.get(field, metadata.get(field))
        if value is not None:
            output[field] = value
    neighbor_element_ids = _alias_values(
        payload.get("neighbor_element_ids")
        or metadata.get("neighbor_element_ids")
        or metadata.get("neighbors")
    )
    if neighbor_element_ids:
        output["neighbor_element_ids"] = neighbor_element_ids
    duplicate_evidence_ids = _alias_values(payload.get("duplicate_evidence_ids"))
    if duplicate_evidence_ids:
        output["duplicate_evidence_ids"] = duplicate_evidence_ids
    element_id_aliases = _alias_values(payload.get("element_id_aliases"))
    if element_id_aliases:
        output["element_id_aliases"] = element_id_aliases
    element_type_aliases = _alias_values(payload.get("element_type_aliases"))
    if element_type_aliases:
        output["element_type_aliases"] = element_type_aliases
    return output


def _source_backrefs(
    payload: dict[str, Any], file_id: str, page_label: str
) -> list[str]:
    backrefs = [
        str(item).strip()
        for item in payload.get("source_backrefs") or []
        if str(item).strip()
    ]
    return backrefs or [f"{file_id}#page:{page_label}"]


def _alias_values(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    else:
        values = []
    output: list[str] = []
    for item in values:
        text = str(item or "").strip()
        if text and text not in output:
            output.append(text)
    return output


def _unique_element_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for record in records:
        evidence_id = str(record.get("evidence_id") or "").strip()
        if not evidence_id or evidence_id in seen:
            continue
        seen.add(evidence_id)
        output.append(record)
    return output


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
