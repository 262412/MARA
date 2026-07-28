from __future__ import annotations

from typing import Any


def dict_list(value: Any) -> list[dict[str, Any]]:
    values = value if isinstance(value, (list, tuple)) else []
    return [dict(item) for item in values if isinstance(item, dict)]


def evidence_representations(item: dict[str, Any]) -> list[dict[str, Any]]:
    representations = dict_list(item.get("representations"))
    item_modality = str(item.get("modality") or "text").strip() or "text"
    modality_by_field = {
        "text": item_modality,
        "ocr_text": "ocr",
        "vlm_text": "vlm",
        "caption": "caption",
    }
    for field, modality in modality_by_field.items():
        text = str(item.get(field) or "").strip()
        if text:
            representations.append({"modality": modality, "field": field, "text": text})
    return stable_dict_union([], representations)


def representation_texts(item: dict[str, Any]) -> list[str]:
    return list(
        dict.fromkeys(
            str(value.get("text") or "").strip()
            for value in evidence_representations(item)
            if str(value.get("text") or "").strip()
        )
    )


def stable_dict_union(left: Any, right: Any) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in [*dict_list(left), *dict_list(right)]:
        key = repr(sorted(item.items()))
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output
