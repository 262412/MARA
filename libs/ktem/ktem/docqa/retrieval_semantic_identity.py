from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from typing import Any

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
    re.IGNORECASE,
)


def semantic_retrieval_identity(value: dict[str, Any]) -> str | None:
    """Return a source-UUID-independent identity for retrieved evidence."""

    metadata = value.get("metadata")
    nested = metadata if isinstance(metadata, dict) else {}

    def field(*names: str) -> str:
        for name in names:
            for container in (value, nested):
                raw = container.get(name)
                if raw not in (None, ""):
                    return str(raw).strip()
        return ""

    text = "\n".join(
        dict.fromkeys(
            normalized
            for normalized in (
                _normalized_text(field(name))
                for name in ("text", "ocr_text", "vlm_text", "caption")
            )
            if normalized
        )
    )
    text_hash = field("normalized_text_hash") or _hash(text)
    runtime_source_id = field("runtime_source_id", "source_id", "file_id")
    structure = {
        "cell_id": field("cell_id"),
        "table_id": field("table_id"),
        "row_index": field("row_index", "row"),
        "column_index": field("column_index", "column", "col"),
        "section_id": field("section_id"),
        "chunk_start": field("chunk_start", "start_char", "start"),
        "chunk_end": field("chunk_end", "end_char", "end"),
        "span_id": _stable_locator(field("span_id"), runtime_source_id),
        "element_id": _stable_locator(field("element_id"), runtime_source_id),
        "modality": field("modality"),
    }
    structure = {name: item for name, item in structure.items() if item}
    document_id = _stable_document_id(field)
    if not document_id:
        return None
    if not text_hash and not structure:
        fallback_id = field("evidence_id", "doc_id", "span_id", "element_id")
        return (
            f"retrieval-id:{_hash_payload({'document_id': document_id, 'id': fallback_id})}"
            if fallback_id
            else None
        )
    payload = {
        "document_id": document_id,
        "text_hash": text_hash,
        "page_label": field("page_label", "page_number", "page", "page_idx"),
        "structure": structure,
    }
    return f"retrieval-semantic:{_hash_payload(payload)}"


def _normalized_text(value: Any) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(normalized.casefold().split())


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest() if value else ""


def _hash_payload(payload: dict[str, Any]) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _stable_document_id(field: Any) -> str:
    canonical = field(
        "evaluation_source_id",
        "canonical_document_id",
        "canonical_dataset_id",
    )
    if canonical:
        return canonical
    document_id = field("document_id")
    return "" if _looks_like_uuid(document_id) else document_id


def _looks_like_uuid(value: str) -> bool:
    return bool(_UUID_RE.fullmatch(value))


def _stable_locator(value: str, runtime_source_id: str) -> str:
    locator = str(value or "").strip()
    if runtime_source_id:
        locator = locator.replace(runtime_source_id, "<source>")
    return locator
