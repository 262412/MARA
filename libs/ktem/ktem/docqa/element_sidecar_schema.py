from __future__ import annotations

from typing import Any, Iterable

ELEMENT_SIDECAR_SCHEMA_VERSION = "1"
LEGACY_ELEMENT_SIDECAR_SCHEMA_VERSION = "legacy"


def sidecar_schema_report(payload: Any) -> dict[str, Any]:
    counts: dict[str, int] = {}
    errors = []
    total_elements = 0
    for index, record in enumerate(iter_sidecar_record_payloads(payload)):
        error = _record_error(record)
        if error:
            errors.append({"record_index": index, "error": error})
            continue
        modality = sidecar_record_modality(record)
        counts[modality] = counts.get(modality, 0) + 1
        total_elements += 1
    return {
        "schema_version": sidecar_schema_version(payload),
        "parser_backend": sidecar_parser_backend(payload),
        "total_elements": total_elements,
        "element_counts_by_modality": dict(sorted(counts.items())),
        "errors": errors,
    }


def iter_sidecar_record_payloads(payload: Any) -> Iterable[dict[str, Any]]:
    if isinstance(payload, list):
        yield from (item for item in payload if isinstance(item, dict))
        return
    if not isinstance(payload, dict):
        return

    yield from _record_list(payload, page_context={})
    for page in payload.get("pages") or []:
        if not isinstance(page, dict):
            continue
        page_context = {"page_label": sidecar_page_label(page)}
        yield from _record_list(page, page_context=page_context)


def sidecar_schema_version(payload: Any) -> str:
    if not isinstance(payload, dict):
        return LEGACY_ELEMENT_SIDECAR_SCHEMA_VERSION
    value = str(payload.get("schema_version") or "").strip()
    return value or LEGACY_ELEMENT_SIDECAR_SCHEMA_VERSION


def sidecar_parser_backend(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    return str(payload.get("parser_backend") or payload.get("parser") or "").strip()


def sidecar_page_label(record: dict[str, Any]) -> str:
    return str(
        record.get("page_label")
        or record.get("page")
        or record.get("page_number")
        or ""
    ).strip()


def sidecar_record_modality(record: dict[str, Any]) -> str:
    value = str(
        record.get("modality") or record.get("element_type") or record.get("type") or ""
    ).strip()
    normalized = value.lower()
    return {"image": "figure", "ocr": "text"}.get(normalized, normalized)


def sidecar_record_text(record: dict[str, Any]) -> str:
    return str(
        record.get("text")
        or record.get("ocr_text")
        or record.get("content")
        or record.get("value")
        or ""
    ).strip()


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


def _record_error(record: dict[str, Any]) -> str:
    if not sidecar_page_label(record):
        return "missing_page_label"
    if not sidecar_record_modality(record):
        return "missing_modality"
    if not sidecar_record_text(record) and not str(record.get("caption") or "").strip():
        return "missing_text_or_caption"
    return ""


def _looks_like_record(container: dict[str, Any]) -> bool:
    return any(key in container for key in ("text", "ocr_text", "caption", "bbox"))
