from __future__ import annotations

import copy
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from ktem.docqa.element_record_contract import element_record_from_mapping
from ktem.docqa.evidence_record_identity import unique_evidence_records

from .ocr_layout_sidecars import build_pdf_ocr_layout_sidecar
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
    return _element_index_records_from_documents(
        documents,
        produce_pdf_ocr_layout=False,
    )


def mmdoc_element_index_records_from_documents(
    documents: list[BenchmarkDocument],
) -> list[dict[str, Any]]:
    return _element_index_records_from_documents(
        documents,
        produce_pdf_ocr_layout=True,
    )


def _element_index_records_from_documents(
    documents: list[BenchmarkDocument],
    *,
    produce_pdf_ocr_layout: bool,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for document in documents:
        offline_records = _offline_element_records(document)
        records.extend(offline_records)
        if (
            produce_pdf_ocr_layout
            and not offline_records
            and document.path.suffix.lower() == ".pdf"
        ):
            records.extend(_pdf_ocr_element_records(document))
        for payload in _document_element_payloads(document):
            record = _element_index_record_from_payload(
                document, payload, len(records) + 1
            )
            if record is not None:
                records.append(record)
    return unique_evidence_records(records)


def _pdf_ocr_element_records(document: BenchmarkDocument) -> list[dict[str, Any]]:
    path = Path(document.path)
    file_stat = path.stat()
    resolved_path = str(path.resolve())
    payloads = _cached_pdf_ocr_layout_elements(
        resolved_path,
        int(file_stat.st_size),
        int(file_stat.st_mtime_ns),
        str(document.document_id),
    )
    records: list[dict[str, Any]] = []
    for index, payload in enumerate(payloads, start=1):
        record = _element_index_record_from_payload(
            document, copy.deepcopy(payload), index
        )
        if record is not None:
            records.append(record)
    return records


@lru_cache(maxsize=8)
def _cached_pdf_ocr_layout_elements(
    resolved_path: str,
    file_size: int,
    modified_ns: int,
    document_id: str,
) -> tuple[dict[str, Any], ...]:
    del file_size, modified_ns
    sidecar = build_pdf_ocr_layout_sidecar(
        resolved_path,
        document_id=document_id,
    )
    return tuple(
        copy.deepcopy(payload)
        for payload in sidecar.get("layout_elements") or []
        if isinstance(payload, dict)
    )


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
    evidence_id = str(
        payload.get("evidence_id") or f"element:{file_id}:{page_label}:{element_id}"
    )
    metadata = dict(payload.get("metadata") or {})
    for key in (
        "visual_extractions",
        "structured_visual_evidence",
        "table_cells",
        "ocr_cells",
        "vlm_cells",
    ):
        if key in payload and key not in metadata:
            metadata[key] = payload[key]
    normalized_payload = {**payload, "metadata": metadata}
    return element_record_from_mapping(
        normalized_payload,
        default_file_id=file_id,
        default_file_name=file_name,
        default_page_label=page_label,
        default_element_id=element_id,
        default_modality=str(
            payload.get("modality") or payload.get("element_type") or "element"
        ),
        default_evidence_id=evidence_id,
    )


def _add_element_contract_fields(
    output: dict[str, Any],
    payload: dict[str, Any],
    metadata: dict[str, Any],
) -> None:
    for field in (
        "parent_element_id",
        "section_id",
        "table_id",
        "continuation_id",
        "normalized_text_hash",
        "cell_id",
        "span_id",
        "row_label",
        "column_label",
        "period",
        "period_kind",
        "value",
        "unit",
        "scale",
        "currency",
        "statement_kind",
        "financial_scope",
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
