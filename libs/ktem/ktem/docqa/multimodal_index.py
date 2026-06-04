from __future__ import annotations

import hashlib
import json
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

from kotaemon.base import Document

from .element_parser import parse_element_index_record

logger = logging.getLogger(__name__)
ELEMENT_INDEX_DOC_TYPE = "mara_element_index"
ELEMENT_INDEX_RELATION_TYPE = "element_index"
ELEMENT_INDEX_SCHEMA_VERSION = "1.0"


def page_image_records_from_documents(documents: Iterable[Any]) -> list[dict[str, Any]]:
    """Build page-image evidence records from indexed thumbnail documents."""
    thumbnails: list[dict[str, Any]] = []
    page_text: dict[tuple[str, str], list[str]] = defaultdict(list)

    for doc in documents:
        metadata = _metadata(doc)
        file_id = _file_id(metadata)
        page_label = _page_label(metadata)
        if not file_id or not page_label:
            continue

        if metadata.get("type") == "thumbnail":
            thumbnails.append(
                {
                    "file_id": file_id,
                    "file_name": _file_name(metadata),
                    "page_label": page_label,
                    "thumbnail_doc_id": _doc_id(doc),
                    "image_ref": str(
                        metadata.get("image_origin") or metadata.get("image_ref") or ""
                    ),
                    "visual_metadata": _visual_metadata(metadata),
                }
            )
        else:
            text = _text(doc, metadata)
            if text:
                page_text[(file_id, page_label)].append(text)

    return [_page_record(item, page_text) for item in thumbnails]


def element_records_from_documents(documents: Iterable[Any]) -> list[dict[str, Any]]:
    """Build layout-element evidence records from indexed document metadata."""
    records = []
    for doc in documents:
        metadata = _metadata(doc)
        if metadata.get("type") == "thumbnail":
            continue
        element_id = str(metadata.get("element_id") or "").strip()
        file_id = _file_id(metadata)
        page_label = _page_label(metadata)
        if not file_id or not page_label:
            continue
        if element_id:
            records.append(
                _element_record(doc, metadata, file_id, page_label, element_id)
            )
            continue
        record = parse_element_index_record(
            doc_id=_doc_id(doc),
            file_id=file_id,
            file_name=_file_name(metadata),
            page_label=page_label,
            text=_text(doc, metadata),
            metadata=metadata,
        )
        if record is not None:
            records.append(record)
    return records


def element_records_from_index_documents(
    documents: Iterable[Any],
) -> list[dict[str, Any]]:
    """Read persisted layout-element records from element-index documents."""
    records = []
    seen: set[str] = set()
    for doc in documents:
        metadata = _metadata(doc)
        if metadata.get("type") != ELEMENT_INDEX_DOC_TYPE:
            continue
        record = _persisted_element_record(metadata.get("element_index_record"))
        if record is None or record["evidence_id"] in seen:
            continue
        seen.add(record["evidence_id"])
        records.append(record)
    return records


def element_index_documents_from_documents(
    file_id: str,
    documents: Iterable[Any],
) -> list[Document]:
    """Build DocStore documents for a persisted layout-element index."""
    return element_index_documents_from_records(
        file_id,
        element_records_from_documents(documents),
    )


def element_index_documents_from_records(
    file_id: str,
    records: Iterable[dict[str, Any]],
) -> list[Document]:
    source_id = str(file_id or "").strip()
    documents = []
    for record in _unique_element_records(records):
        metadata = {
            "type": ELEMENT_INDEX_DOC_TYPE,
            "source_id": source_id,
            "file_id": record["file_id"],
            "file_name": record["file_name"],
            "page_label": record["page_label"],
            "element_index_relation_type": ELEMENT_INDEX_RELATION_TYPE,
            "element_index_schema_version": ELEMENT_INDEX_SCHEMA_VERSION,
            "element_index_record": record,
        }
        documents.append(
            Document(
                text=_element_index_text(record),
                id_=_element_index_doc_id(source_id, record),
                metadata=metadata,
            )
        )
    return documents


def _page_record(
    thumbnail: dict[str, Any],
    page_text: dict[tuple[str, str], list[str]],
) -> dict[str, Any]:
    file_id = thumbnail["file_id"]
    file_name = thumbnail["file_name"]
    page_label = thumbnail["page_label"]
    thumbnail_doc_id = thumbnail["thumbnail_doc_id"]
    image_ref = thumbnail["image_ref"]
    text = "\n".join(page_text.get((file_id, page_label), []))
    metadata = dict(thumbnail["visual_metadata"])
    if image_ref:
        metadata["image_ref"] = image_ref
    if thumbnail_doc_id:
        metadata["thumbnail_doc_id"] = thumbnail_doc_id
    metadata.setdefault("visual_backend_type", "local_smoke")
    return {
        "evidence_id": f"page-image:{file_id}:{page_label}",
        "file_id": file_id,
        "file_name": file_name,
        "page_label": page_label,
        "page_number": _page_number(page_label),
        "page_image_path": image_ref,
        "page_visual_embedding": metadata.get("visual_embedding"),
        "late_interaction_tokens": list(metadata.get("late_interaction_tokens") or []),
        "modality": "page_image",
        "text": text,
        "ocr_text": text,
        "source_backrefs": [f"{file_id}#page:{page_label}"],
        "metadata": metadata,
    }


def build_local_page_image_records(
    file_records: Iterable[dict[str, Any]],
    *,
    page_numbers: list[int] | None = None,
    renderer: Any | None = None,
    text_extractor: Any | None = None,
    dpi: int = 120,
) -> list[dict[str, Any]]:
    """Render local PDF pages into deterministic smoke page-image records."""
    records: list[dict[str, Any]] = []
    for file_record in file_records:
        if not _is_pdf_record(file_record):
            continue
        file_path = Path(str(file_record.get("path") or file_record.get("file_path")))
        pages = _requested_pages(file_path, page_numbers)
        if not pages:
            continue
        images = _render_pages(file_path, pages, renderer=renderer, dpi=dpi)
        for page_number, image_ref in zip(pages, images):
            records.append(
                _local_page_record(
                    file_record,
                    page_number,
                    str(image_ref or ""),
                    text_extractor=text_extractor,
                )
            )
    return records


def _element_record(
    doc: Any,
    metadata: dict[str, Any],
    file_id: str,
    page_label: str,
    element_id: str,
) -> dict[str, Any]:
    element_metadata = dict(metadata.get("element_metadata") or {})
    return {
        "evidence_id": f"element:{file_id}:{page_label}:{element_id}",
        "file_id": file_id,
        "file_name": _file_name(metadata),
        "page_label": page_label,
        "element_id": element_id,
        "modality": _element_modality(metadata),
        "bbox": metadata.get("bbox"),
        "caption": str(metadata.get("caption") or "").strip(),
        "text": _text(doc, metadata),
        "source_backrefs": [f"{file_id}#page:{page_label}"],
        "metadata": element_metadata,
    }


def _persisted_element_record(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    evidence_id = str(value.get("evidence_id") or "").strip()
    file_id = str(value.get("file_id") or value.get("source_id") or "").strip()
    page_label = str(value.get("page_label") or value.get("page") or "").strip()
    element_id = str(value.get("element_id") or "").strip()
    if not evidence_id or not file_id or not page_label or not element_id:
        return None
    raw_metadata = value.get("metadata")
    metadata = raw_metadata if isinstance(raw_metadata, dict) else {}
    return {
        "evidence_id": evidence_id,
        "file_id": file_id,
        "file_name": str(value.get("file_name") or value.get("source_name") or ""),
        "page_label": page_label,
        "element_id": element_id,
        "modality": str(
            value.get("modality") or value.get("element_type") or "element"
        ),
        "bbox": value.get("bbox"),
        "caption": str(value.get("caption") or ""),
        "text": str(value.get("text") or ""),
        "source_backrefs": _source_backrefs(value, file_id, page_label),
        "metadata": dict(metadata),
    }


def _unique_element_records(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    unique = []
    seen: set[str] = set()
    for record in records:
        normalized = _persisted_element_record(record)
        if normalized is None or normalized["evidence_id"] in seen:
            continue
        seen.add(normalized["evidence_id"])
        unique.append(normalized)
    return unique


def _source_backrefs(value: dict[str, Any], file_id: str, page_label: str) -> list[str]:
    backrefs = [
        str(item).strip()
        for item in value.get("source_backrefs") or []
        if str(item).strip()
    ]
    return backrefs or [f"{file_id}#page:{page_label}"]


def _element_index_text(record: dict[str, Any]) -> str:
    return str(record.get("text") or record.get("caption") or "").strip()


def _element_index_doc_id(file_id: str, record: dict[str, Any]) -> str:
    payload = json.dumps(record, sort_keys=True, default=str)
    digest = hashlib.sha256(f"{file_id}\n{payload}".encode("utf-8")).hexdigest()
    return f"element-index:{file_id}:{digest[:16]}"


def _metadata(doc: Any) -> dict[str, Any]:
    metadata = getattr(doc, "metadata", None)
    return metadata if isinstance(metadata, dict) else {}


def _doc_id(doc: Any) -> str:
    return str(getattr(doc, "doc_id", None) or getattr(doc, "id_", None) or "").strip()


def _file_id(metadata: dict[str, Any]) -> str:
    return str(metadata.get("file_id") or metadata.get("source_id") or "").strip()


def _file_name(metadata: dict[str, Any]) -> str:
    return str(metadata.get("file_name") or metadata.get("source_name") or "").strip()


def _page_label(metadata: dict[str, Any]) -> str:
    return str(metadata.get("page_label") or metadata.get("page") or "").strip()


def _page_number(page_label: str) -> int | None:
    try:
        return int(str(page_label).strip())
    except ValueError:
        return None


def _text(doc: Any, metadata: dict[str, Any]) -> str:
    return str(getattr(doc, "text", None) or metadata.get("text") or "").strip()


def _element_modality(metadata: dict[str, Any]) -> str:
    return str(
        metadata.get("modality") or metadata.get("element_type") or "element"
    ).strip()


def _visual_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        key: metadata[key]
        for key in (
            "visual_embedding",
            "visual_embedding_model",
            "late_interaction_tokens",
            "visual_retriever",
        )
        if key in metadata
    }


def _is_pdf_record(file_record: dict[str, Any]) -> bool:
    file_name = str(file_record.get("file_name") or file_record.get("name") or "")
    file_path = str(file_record.get("path") or file_record.get("file_path") or "")
    return Path(file_name or file_path).suffix.lower() == ".pdf"


def _requested_pages(file_path: Path, page_numbers: list[int] | None) -> list[int]:
    if page_numbers:
        return sorted({max(1, int(page)) for page in page_numbers})
    page_count = _pdf_page_count(file_path)
    return list(range(1, page_count + 1))


def _pdf_page_count(file_path: Path) -> int:
    try:
        from pypdf import PdfReader

        return max(0, len(PdfReader(str(file_path), strict=False).pages))
    except Exception as exc:
        logger.warning("Failed to count PDF pages for local image index: %s", exc)
        return 0


def _render_pages(
    file_path: Path,
    pages: list[int],
    *,
    renderer: Any | None,
    dpi: int,
) -> list[str]:
    render_fn = renderer or _default_page_renderer
    zero_based_pages = [page - 1 for page in pages]
    try:
        return list(render_fn(file_path, zero_based_pages, dpi))
    except Exception as exc:
        logger.warning("Failed to render PDF pages for local image index: %s", exc)
        return []


def _default_page_renderer(file_path: Path, pages: list[int], dpi: int) -> list[str]:
    from kotaemon.loaders.pdf_loader import get_page_thumbnails

    return list(get_page_thumbnails(file_path, pages, dpi=dpi))


def _local_page_record(
    file_record: dict[str, Any],
    page_number: int,
    image_ref: str,
    *,
    text_extractor: Any | None,
) -> dict[str, Any]:
    file_id = str(file_record.get("file_id") or file_record.get("id") or "").strip()
    file_name = str(file_record.get("file_name") or file_record.get("name") or "")
    file_path = Path(str(file_record.get("path") or file_record.get("file_path")))
    page_label = str(page_number)
    page_text = _extract_page_text(file_path, page_number, text_extractor)
    tokens = _late_interaction_tokens(page_text)
    metadata = {
        "image_ref": image_ref,
        "visual_backend_type": "local_smoke",
        "visual_embedding_model": "deterministic_token_hash_v1",
        "late_interaction_tokens": tokens,
    }
    return {
        "evidence_id": f"page-image:{file_id}:{page_label}",
        "file_id": file_id,
        "file_name": file_name,
        "page_label": page_label,
        "page_number": page_number,
        "page_image_path": image_ref,
        "page_visual_embedding": _deterministic_embedding(tokens),
        "late_interaction_tokens": tokens,
        "modality": "page_image",
        "text": page_text,
        "ocr_text": page_text,
        "source_backrefs": [f"{file_id}#page:{page_label}"],
        "metadata": metadata,
    }


def _extract_page_text(
    file_path: Path, page_number: int, text_extractor: Any | None
) -> str:
    if text_extractor is not None:
        return str(text_extractor(file_path, page_number) or "").strip()
    try:
        from pypdf import PdfReader

        pages = PdfReader(str(file_path), strict=False).pages
        page = pages[page_number - 1]
        return " ".join(str(page.extract_text() or "").split())
    except Exception as exc:
        logger.warning("Failed to extract PDF page text for local image index: %s", exc)
        return ""


def _late_interaction_tokens(*values: str) -> list[str]:
    tokens = {
        token
        for value in values
        for token in re.findall(r"[a-zA-Z0-9]+", str(value or "").lower())
        if len(token) > 2
    }
    return sorted(tokens)[:64]


def _deterministic_embedding(tokens: list[str], dimensions: int = 16) -> list[float]:
    buckets = [0.0 for _ in range(dimensions)]
    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        buckets[digest[0] % dimensions] += 1.0
    total = sum(buckets) or 1.0
    return [round(value / total, 6) for value in buckets]
