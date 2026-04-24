from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping


@dataclass(frozen=True)
class CitationTarget:
    """Structured navigation target for a cited document span or element."""

    doc_id: str | None
    source_id: str | None = None
    file_name: str | None = None
    page_number: int | None = None
    page_label: str | None = None
    bbox: tuple[float, ...] | None = None
    element_id: str | None = None
    parent_element_id: str | None = None
    element_type: str | None = "text"
    span_start: int | None = None
    span_end: int | None = None
    highlight_text: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def citation_target_from_document(
    document: Any, span: Mapping[str, Any] | tuple[Any, Any] | list[Any] | None = None
) -> CitationTarget:
    """Create a structured citation target from a retrieved/base document."""

    metadata = dict(getattr(document, "metadata", None) or {})
    span_start, span_end = _span_offsets(span)

    return CitationTarget(
        doc_id=_string_or_none(getattr(document, "doc_id", None)),
        source_id=_string_or_none(
            _metadata_first(metadata, "source_id", "source", "doc_id", "file_path")
            or getattr(document, "source", None)
        ),
        file_name=_string_or_none(_metadata_first(metadata, "file_name", "filename")),
        page_number=_normalize_int(
            _metadata_first(metadata, "page_number", "page", "page_idx")
        ),
        page_label=_string_or_none(metadata.get("page_label")),
        bbox=_normalize_bbox(_metadata_first(metadata, "bbox", "box", "bounding_box")),
        element_id=_string_or_none(metadata.get("element_id")),
        parent_element_id=_string_or_none(
            _metadata_first(metadata, "parent_element_id", "parent_id")
        ),
        element_type=_normalize_element_type(
            _metadata_first(metadata, "element_type", "type")
        ),
        span_start=span_start,
        span_end=span_end,
        highlight_text=_highlight_text(document, span_start, span_end),
    )


def citation_targets_from_spans(
    spans: Mapping[str, Iterable[Mapping[str, Any] | tuple[Any, Any] | list[Any]]],
    docs: Iterable[Any],
) -> list[CitationTarget]:
    """Build citation targets from prepare_citations-compatible span mappings."""

    id_to_doc = {_string_or_none(getattr(doc, "doc_id", None)): doc for doc in docs}
    targets: list[CitationTarget] = []

    for doc_id, doc_spans in spans.items():
        doc = id_to_doc.get(str(doc_id))
        if doc is None:
            continue
        for span in doc_spans:
            targets.append(citation_target_from_document(doc, span))

    return targets


def _metadata_first(metadata: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in metadata and metadata[key] is not None:
            return metadata[key]
    return None


def _normalize_bbox(value: Any) -> tuple[float, ...] | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            value = value.split(",")
    if isinstance(value, dict):
        keys = ("x0", "y0", "x1", "y1")
        if not all(key in value for key in keys):
            return None
        value = [value[key] for key in keys]
    try:
        return tuple(float(item) for item in value)
    except (TypeError, ValueError):
        return None


def _normalize_element_type(value: Any) -> str:
    element_type = str(value or "text").strip().lower()
    if element_type == "image":
        return "figure"
    if element_type:
        return element_type
    return "text"


def _normalize_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _span_offsets(
    span: Mapping[str, Any] | tuple[Any, Any] | list[Any] | None,
) -> tuple[int | None, int | None]:
    if span is None:
        return None, None
    if isinstance(span, Mapping):
        return _normalize_int(span.get("start")), _normalize_int(span.get("end"))
    if isinstance(span, (tuple, list)) and len(span) >= 2:
        return _normalize_int(span[0]), _normalize_int(span[1])
    return None, None


def _highlight_text(
    document: Any, span_start: int | None, span_end: int | None
) -> str | None:
    if span_start is None or span_end is None:
        return None
    if span_end < span_start:
        return None
    return _document_text(document)[span_start:span_end]


def _document_text(document: Any) -> str:
    text = getattr(document, "text", None)
    if text is not None:
        return str(text)
    content = getattr(document, "content", "")
    return "" if content is None else str(content)


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    return value or None
