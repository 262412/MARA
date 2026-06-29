from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from .element_parser import ELEMENT_SCHEMA_VERSION

SIDECAR_SUFFIXES = (
    ".mara-elements.json",
    ".elements.json",
    ".layout.json",
)
_CONSUMED_FILE_IDS: set[str] = set()


def offline_element_records_for_file(
    *,
    file_id: str,
    file_name: str,
    file_path: str | Path,
) -> list[dict[str, Any]]:
    """Read same-file offline OCR/layout sidecars into element-index records."""

    records: list[dict[str, Any]] = []
    for sidecar_path in offline_layout_sidecar_paths(file_path):
        payload = _read_sidecar(sidecar_path)
        records.extend(
            _records_from_payload(
                payload,
                file_id=str(file_id),
                file_name=str(file_name),
                sidecar_path=sidecar_path,
            )
        )
    return records


def offline_element_records_for_documents(
    *,
    file_id: str,
    documents: Iterable[Any],
) -> list[dict[str, Any]]:
    source = _source_from_documents(documents)
    source_id = str(file_id)
    if source is None or source_id in _CONSUMED_FILE_IDS:
        return []
    records = offline_element_records_for_file(
        file_id=source_id,
        file_name=source["file_name"],
        file_path=source["file_path"],
    )
    _CONSUMED_FILE_IDS.add(source_id)
    return records


def offline_layout_sidecar_paths(file_path: str | Path) -> list[Path]:
    path = Path(file_path)
    candidates = []
    for suffix in SIDECAR_SUFFIXES:
        candidates.append(Path(f"{path}{suffix}"))
        candidates.append(path.with_name(f"{path.stem}{suffix}"))
    return _existing_unique_paths(candidates)


def _read_sidecar(sidecar_path: Path) -> Any:
    try:
        return json.loads(sidecar_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid offline layout sidecar JSON: {sidecar_path}"
        ) from exc


def _records_from_payload(
    payload: Any,
    *,
    file_id: str,
    file_name: str,
    sidecar_path: Path,
) -> list[dict[str, Any]]:
    records = []
    parser = _parser_name(payload)
    for index, item in enumerate(_iter_record_payloads(payload)):
        record = _normalize_record(
            item,
            file_id=file_id,
            file_name=file_name,
            sidecar_name=sidecar_path.name,
            parser=parser,
            record_index=index,
        )
        if record is not None:
            records.append(record)
    return records


def _iter_record_payloads(payload: Any) -> Iterable[dict[str, Any]]:
    if isinstance(payload, list):
        yield from (item for item in payload if isinstance(item, dict))
        return
    if not isinstance(payload, dict):
        return

    yield from _record_list(payload, page_context={})
    for page in payload.get("pages") or []:
        if not isinstance(page, dict):
            continue
        page_context = {"page_label": _page_label_from(page)}
        yield from _record_list(page, page_context=page_context)


def _record_list(
    container: dict[str, Any],
    *,
    page_context: dict[str, str],
) -> Iterable[dict[str, Any]]:
    for key in (
        "element_index_records",
        "layout_elements",
        "elements",
        "element_index",
    ):
        value = container.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    yield {**page_context, **item}
            return
    if _looks_like_record(container):
        yield {**page_context, **container}


def _normalize_record(
    record: dict[str, Any],
    *,
    file_id: str,
    file_name: str,
    sidecar_name: str,
    parser: str,
    record_index: int,
) -> dict[str, Any] | None:
    page_label = _page_label_from(record)
    modality = _modality(record)
    text = _text(record)
    caption = str(record.get("caption") or "").strip()
    if not page_label or not modality or not (text or caption):
        return None

    element_id = _element_id(record, modality, page_label, record_index)
    evidence_id = (
        str(record.get("evidence_id") or "").strip()
        or f"element:{file_id}:{page_label}:{element_id}"
    )
    return {
        "evidence_id": evidence_id,
        "file_id": file_id,
        "file_name": file_name,
        "page_label": page_label,
        "element_id": element_id,
        "modality": modality,
        "bbox": _bbox(record),
        "caption": caption,
        "text": text,
        "source_backrefs": _source_backrefs(record, file_id, page_label),
        "metadata": _metadata(record, sidecar_name, parser, record_index),
    }


def _metadata(
    record: dict[str, Any],
    sidecar_name: str,
    parser: str,
    record_index: int,
) -> dict[str, Any]:
    raw_metadata = record.get("metadata")
    metadata = dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
    metadata.setdefault("element_schema_version", ELEMENT_SCHEMA_VERSION)
    metadata.setdefault("index_source", "offline_layout_sidecar")
    metadata.setdefault("offline_layout_record_index", record_index)
    metadata.setdefault("offline_layout_sidecar", sidecar_name)
    if parser:
        metadata.setdefault("parser_backend", parser)
    return metadata


def _existing_unique_paths(candidates: Iterable[Path]) -> list[Path]:
    paths = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved in seen or not candidate.is_file():
            continue
        seen.add(resolved)
        paths.append(candidate)
    return paths


def _source_from_documents(documents: Iterable[Any]) -> dict[str, str] | None:
    for document in documents:
        metadata = getattr(document, "metadata", None)
        if not isinstance(metadata, dict):
            continue
        file_path = str(metadata.get("file_path") or "").strip()
        file_name = str(metadata.get("file_name") or "").strip()
        if file_path and file_name:
            return {"file_path": file_path, "file_name": file_name}
    return None


def _parser_name(payload: Any) -> str:
    if isinstance(payload, dict):
        return str(payload.get("parser") or payload.get("parser_backend") or "").strip()
    return ""


def _page_label_from(record: dict[str, Any]) -> str:
    return str(
        record.get("page_label")
        or record.get("page")
        or record.get("page_number")
        or ""
    ).strip()


def _modality(record: dict[str, Any]) -> str:
    value = str(
        record.get("modality")
        or record.get("element_type")
        or record.get("type")
        or "element"
    ).strip()
    normalized = value.lower()
    return {"image": "figure", "ocr": "text"}.get(normalized, normalized)


def _text(record: dict[str, Any]) -> str:
    return str(
        record.get("text")
        or record.get("ocr_text")
        or record.get("content")
        or record.get("value")
        or ""
    ).strip()


def _bbox(record: dict[str, Any]) -> Any:
    return record.get("bbox") or record.get("box") or record.get("bounding_box")


def _element_id(
    record: dict[str, Any],
    modality: str,
    page_label: str,
    record_index: int,
) -> str:
    existing = str(record.get("element_id") or record.get("id") or "").strip()
    if existing:
        return existing
    return f"{_slug(modality) or 'element'}-{_slug(page_label) or 'page'}-{record_index + 1}"


def _source_backrefs(
    record: dict[str, Any],
    file_id: str,
    page_label: str,
) -> list[str]:
    raw_backrefs = record.get("source_backrefs")
    if isinstance(raw_backrefs, str):
        raw_backrefs = [raw_backrefs]
    backrefs = [str(item).strip() for item in raw_backrefs or [] if str(item).strip()]
    return backrefs or [f"{file_id}#page:{page_label}"]


def _looks_like_record(container: dict[str, Any]) -> bool:
    return any(key in container for key in ("text", "ocr_text", "caption", "bbox"))


def _slug(value: str) -> str:
    return "-".join(
        token
        for token in re.findall(r"[a-zA-Z0-9]+", str(value or "").lower())
        if token
    )
