from __future__ import annotations

from typing import Any


def merged_locator_metadata(
    evidence_metadata: dict[str, Any],
    items: list[dict[str, Any]],
) -> dict[str, list[str]]:
    derived = _selected_locator_metadata(items)
    return {
        key: values or _coerce_locator_values(evidence_metadata.get(key))
        for key, values in derived.items()
    }


def _selected_locator_metadata(items: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {
        "page_coverage": _unique_selected(_item_page_labels(item) for item in items),
        "source_ids": _unique_selected(_item_source_ids(item) for item in items),
        "evidence_ids": _unique_selected(
            [[str(item.get("evidence_id") or "").strip()] for item in items]
        ),
    }


def _coerce_locator_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if not isinstance(value, (list, tuple, set)):
        return []
    return _unique_selected([value])


def _unique_selected(values: Any) -> list[str]:
    output: list[str] = []
    for group in values:
        for value in group:
            item = str(value or "").strip()
            if item and item not in output:
                output.append(item)
    return output


def _item_page_labels(item: dict[str, Any]) -> list[str]:
    labels = [str(item.get("page_label") or "").strip()]
    labels.extend(
        _page_label_from_backref(ref) for ref in item.get("source_backrefs") or []
    )
    return labels


def _item_source_ids(item: dict[str, Any]) -> list[str]:
    source_ids = [str(item.get("source_id") or "").strip()]
    source_ids.extend(
        _source_id_from_backref(ref) for ref in item.get("source_backrefs") or []
    )
    return source_ids


def _page_label_from_backref(ref: Any) -> str:
    value = str(ref or "")
    if "#page:" not in value:
        return ""
    return value.split("#page:", 1)[1].split("#", 1)[0].strip()


def _source_id_from_backref(ref: Any) -> str:
    value = str(ref or "")
    if "#" not in value:
        return ""
    return value.split("#", 1)[0].strip()
