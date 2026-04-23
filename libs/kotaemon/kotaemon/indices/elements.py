from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Literal

ElementType = Literal[
    "text", "table", "figure", "formula", "page", "thumbnail", "annotation"
]

_TYPE_MAP: dict[str, ElementType] = {
    "text": "text",
    "table": "table",
    "image": "figure",
    "figure": "figure",
    "formula": "formula",
    "page": "page",
    "thumbnail": "thumbnail",
    "annotation": "annotation",
}


@dataclass(frozen=True)
class DocumentElement:
    """Normalized document element metadata for parser and benchmark pipelines."""

    element_id: str
    element_type: ElementType
    text: str = ""
    page_number: int | None = None
    page_label: str | None = None
    bbox: tuple[float, ...] | None = None
    source_id: str | None = None
    file_name: str | None = None
    parser: str | None = None
    confidence: float | None = None
    parent_element_id: str | None = None
    neighbor_element_ids: tuple[str, ...] = ()
    caption: str | None = None
    ocr_text: str | None = None
    table: Any = None
    raw_pdf_text: str | None = None
    normalized_formula: str | None = None
    formula_image: Any = None
    layout_blocks: Any = None
    formula: dict[str, Any] | None = None
    image_origin: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)


def document_to_element(document: Any) -> DocumentElement:
    """Create a normalized DocumentElement from a kotaemon/llama-index Document."""

    metadata = dict(getattr(document, "metadata", None) or {})
    element_type = _normalize_element_type(metadata.get("type"))
    text = _document_text(document)
    if element_type == "formula":
        text = normalize_formula_text(
            _metadata_first(metadata, "normalized_formula", "formula_text", "latex")
            or text
        )

    page_number = _normalize_page_number(
        _metadata_first(metadata, "page_number", "page", "page_idx")
    )
    page_label = _normalize_page_label(metadata.get("page_label"), page_number)
    if page_number is None:
        page_number = _normalize_page_number(page_label)

    bbox = _normalize_bbox(_metadata_first(metadata, "bbox", "box", "bounding_box"))
    source_id = _string_or_none(
        _metadata_first(metadata, "source_id", "source", "doc_id", "file_path")
        or getattr(document, "source", None)
    )
    file_name = _string_or_none(_metadata_first(metadata, "file_name", "filename"))
    parser = _string_or_none(metadata.get("parser"))
    confidence = _normalize_float(metadata.get("confidence"))
    parent_element_id = _string_or_none(
        _metadata_first(metadata, "parent_element_id", "parent_id")
    )
    neighbor_element_ids = _normalize_string_tuple(
        _metadata_first(metadata, "neighbor_element_ids", "neighbors")
    )
    caption = _string_or_none(metadata.get("caption"))
    ocr_text = _string_or_none(_metadata_first(metadata, "ocr_text", "image_text"))
    table = _metadata_first(
        metadata, "table", "table_origin", "table_json", "text_as_html"
    )
    raw_pdf_text = _string_or_none(metadata.get("raw_pdf_text"))
    normalized_formula = text if element_type == "formula" else _string_or_none(
        metadata.get("normalized_formula")
    )
    formula_image = _metadata_first(metadata, "formula_image", "image_origin")
    layout_blocks = metadata.get("layout_blocks")
    formula = _formula_payload(metadata, text) if element_type == "formula" else None
    image_origin = metadata.get("image_origin")

    element_id = _string_or_none(metadata.get("element_id")) or _stable_element_id(
        source_id=source_id,
        page_number=page_number,
        page_label=page_label,
        element_type=element_type,
        text=text,
        bbox=bbox,
    )

    return DocumentElement(
        element_id=element_id,
        element_type=element_type,
        text=text,
        page_number=page_number,
        page_label=page_label,
        bbox=bbox,
        source_id=source_id,
        file_name=file_name,
        parser=parser,
        confidence=confidence,
        parent_element_id=parent_element_id,
        neighbor_element_ids=neighbor_element_ids,
        caption=caption,
        ocr_text=ocr_text,
        table=table,
        raw_pdf_text=raw_pdf_text,
        normalized_formula=normalized_formula,
        formula_image=formula_image,
        layout_blocks=layout_blocks,
        formula=formula,
        image_origin=image_origin,
        metadata=metadata,
    )


def documents_to_elements(documents: list[Any]) -> list[DocumentElement]:
    return [document_to_element(document) for document in documents]


def annotate_document_with_element_metadata(document: Any) -> Any:
    """Attach normalized element metadata before storage/retrieval indexing."""

    element = document_to_element(document)
    metadata = dict(getattr(document, "metadata", None) or {})
    metadata.setdefault("element_id", element.element_id)
    metadata.setdefault("element_type", element.element_type)
    _set_metadata_if_present(metadata, "page_number", element.page_number)
    _set_metadata_if_present(metadata, "page_label", element.page_label)
    if element.bbox is not None:
        metadata["bbox"] = _bbox_to_metadata_value(element.bbox)
    _set_metadata_if_present(metadata, "source_id", element.source_id)
    _set_metadata_if_present(metadata, "file_name", element.file_name)
    _set_metadata_if_present(metadata, "parser", element.parser)
    _set_metadata_if_present(metadata, "confidence", element.confidence)
    _set_metadata_if_present(metadata, "parent_element_id", element.parent_element_id)
    if element.neighbor_element_ids:
        metadata.pop("neighbors", None)
        metadata.pop("neighbor_element_ids", None)
        _set_metadata_json(metadata, "neighbor_element_ids", element.neighbor_element_ids)
    _set_metadata_if_present(metadata, "caption", element.caption)
    _set_metadata_if_present(metadata, "ocr_text", element.ocr_text)
    _set_metadata_if_present(metadata, "raw_pdf_text", element.raw_pdf_text)
    _set_metadata_complex(metadata, "table", element.table)
    _set_metadata_complex(metadata, "layout_blocks", element.layout_blocks)
    _set_metadata_complex(metadata, "formula_image", element.formula_image)
    _set_metadata_complex(metadata, "image_origin", element.image_origin)

    if element.formula is not None:
        metadata["formula_text"] = element.text
        metadata["normalized_formula"] = element.text
        if element.formula.get("format") is not None:
            metadata.setdefault("formula_format", str(element.formula["format"]))
        if "formula" in metadata and not _is_flat_metadata_value(metadata["formula"]):
            _set_metadata_json(metadata, "formula", metadata.pop("formula"))
        _set_document_text(document, element.text)

    _flatten_metadata_for_vector_store(metadata)
    document.metadata = metadata
    return document


def normalize_formula_text(text: Any) -> str:
    """Normalize formula whitespace while preserving LaTeX/math tokens."""

    return re.sub(r"\s+", " ", str(text or "")).strip()


def _normalize_element_type(value: Any) -> ElementType:
    return _TYPE_MAP.get(str(value or "text").strip().lower(), "text")


def _document_text(document: Any) -> str:
    text = getattr(document, "text", None)
    if text is not None:
        return str(text)
    content = getattr(document, "content", "")
    return "" if content is None else str(content)


def _metadata_first(metadata: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in metadata and metadata[key] is not None:
            return metadata[key]
    return None


def _normalize_page_number(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _normalize_page_label(value: Any, page_number: int | None) -> str | None:
    if value is not None:
        label = str(value).strip()
        return label or None
    if page_number is not None:
        return str(page_number)
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
        if all(key in value for key in keys):
            value = [value[key] for key in keys]
        else:
            return None
    try:
        return tuple(float(item) for item in value)
    except (TypeError, ValueError):
        return None


def _normalize_string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return ()
        try:
            value = json.loads(stripped)
        except json.JSONDecodeError:
            value = stripped.split(",")
    if isinstance(value, dict):
        value = value.values()
    try:
        return tuple(
            item
            for item in (_string_or_none(part) for part in value)
            if item is not None
        )
    except TypeError:
        item = _string_or_none(value)
        return (item,) if item is not None else ()


def _normalize_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if text else None


def _set_metadata_if_present(metadata: dict[str, Any], key: str, value: Any) -> None:
    if value is not None:
        metadata.setdefault(key, value)


def _set_metadata_complex(metadata: dict[str, Any], key: str, value: Any) -> None:
    if value is None:
        return
    if _is_flat_metadata_value(value):
        metadata.setdefault(key, value)
        return
    metadata.pop(key, None)
    _set_metadata_json(metadata, key, value)


def _set_metadata_json(metadata: dict[str, Any], key: str, value: Any) -> None:
    metadata[f"{key}_json"] = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )


def _bbox_to_metadata_value(bbox: tuple[float, ...]) -> str:
    return json.dumps(list(bbox), ensure_ascii=False, separators=(",", ":"))


def _is_flat_metadata_value(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float))


def _flatten_metadata_for_vector_store(metadata: dict[str, Any]) -> None:
    for key, value in list(metadata.items()):
        if _is_flat_metadata_value(value):
            continue
        if key.endswith("_json"):
            metadata[key] = json.dumps(
                value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
            continue
        metadata.pop(key)
        _set_metadata_json(metadata, key, value)


def _set_document_text(document: Any, text: str) -> None:
    if hasattr(document, "set_content"):
        document.set_content(text)
    document.text = text
    document.content = text


def _formula_payload(metadata: dict[str, Any], text: str) -> dict[str, Any]:
    formula = metadata.get("formula")
    if isinstance(formula, dict):
        payload = dict(formula)
        payload.setdefault("text", text)
    else:
        payload = {"text": text}
        if formula is not None:
            payload["raw"] = formula

    formula_format = _metadata_first(metadata, "formula_format", "formula_type")
    if formula_format is not None:
        payload["format"] = str(formula_format)
    return payload


def _stable_element_id(
    *,
    source_id: str | None,
    page_number: int | None,
    page_label: str | None,
    element_type: ElementType,
    text: str,
    bbox: tuple[float, ...] | None,
) -> str:
    identity = {
        "source_id": source_id,
        "page": page_number if page_number is not None else page_label,
        "element_type": element_type,
        "text": text,
        "bbox": bbox,
    }
    payload = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
