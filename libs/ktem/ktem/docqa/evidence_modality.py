from __future__ import annotations

_COMPATIBLE_MODALITIES = {
    "figure": {"figure", "image", "chart", "plot", "page_image"},
    "table": {"table", "element", "page_image"},
    "formula": {"formula", "element", "page_image"},
    "slide": {"slide", "page_image"},
    "page_image": {"page_image", "figure", "image", "chart", "plot", "slide"},
}


def modality_matches(required: str, observed: str) -> bool:
    expected = str(required or "auto").strip().lower()
    actual = str(observed or "").strip().lower()
    if expected in {"", "auto"}:
        return True
    return actual == expected or actual in _COMPATIBLE_MODALITIES.get(expected, set())
