from __future__ import annotations

from typing import Any

from kotaemon.base import RetrievedDocument


def _metadata_kind(metadata: dict[str, Any]) -> str:
    for key in ("element_type", "type", "kind", "category", "content_type"):
        value = str(metadata.get(key) or "").strip().lower()
        if value:
            return value
    return ""


def _evidence_metadata(
    evidence_mode: str,
    images: list[Any] | tuple[Any, ...] | None,
    hits: list[RetrievedDocument],
) -> dict[str, Any]:
    image_items = [image for image in images or [] if image is not None]
    kinds = sorted(
        {
            kind
            for hit in hits
            for kind in [_metadata_kind(dict(getattr(hit, "metadata", {}) or {}))]
            if kind
        }
    )
    figure_markers = {
        "chart",
        "diagram",
        "drawing",
        "figure",
        "image",
        "page_image",
        "picture",
        "shape",
        "table_image",
        "thumbnail",
        "visual",
    }
    table_markers = {"cell", "spreadsheet", "table", "table_html", "table_text"}
    formula_markers = {"equation", "formula", "formula_image", "latex", "math"}
    slide_markers = {"deck", "powerpoint", "ppt", "pptx", "slide"}
    visual_keys = {
        "image_path",
        "image_origin",
        "page_image",
        "page_image_path",
        "thumbnail",
        "thumbnail_path",
        "visual_path",
    }
    table_keys = {"table", "table_html", "table_origin", "table_text"}
    formula_keys = {"formula", "formula_text", "latex", "math_text", "tex"}
    slide_keys = {"slide", "slide_number", "slide_title"}

    has_figure = bool(image_items) or any(
        any(marker in kind for marker in figure_markers) for kind in kinds
    )
    has_table = any(any(marker in kind for marker in table_markers) for kind in kinds)
    has_formula = any(
        any(marker in kind for marker in formula_markers) for kind in kinds
    )
    has_slide = any(any(marker in kind for marker in slide_markers) for kind in kinds)
    has_page_visual = bool(image_items)
    for hit in hits:
        metadata = dict(getattr(hit, "metadata", {}) or {})
        if any(metadata.get(key) for key in visual_keys):
            has_figure = True
            has_page_visual = True
        if any(metadata.get(key) for key in table_keys):
            has_table = True
        if any(metadata.get(key) for key in formula_keys):
            has_formula = True
        if any(metadata.get(key) for key in slide_keys):
            has_slide = True

    return {
        "evidence_mode": evidence_mode,
        "image_count": len(image_items),
        "has_images": bool(image_items),
        "has_figure_evidence": has_figure,
        "has_table_evidence": has_table,
        "has_formula_evidence": has_formula,
        "has_slide_evidence": has_slide,
        "has_page_visual_context": has_page_visual,
        "source_kinds": kinds,
    }
