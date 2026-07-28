from __future__ import annotations

from typing import Any


def source_alias_values(
    item: dict[str, Any],
    metadata: dict[str, Any],
    source_id: str,
) -> list[str]:
    source_aliases = item.get("source_aliases") or metadata.get("source_aliases") or []
    if isinstance(source_aliases, str):
        source_aliases = [source_aliases]
    values = [
        source_id,
        item.get("source_name"),
        item.get("file_name"),
        metadata.get("source_name"),
        metadata.get("file_name"),
        *source_aliases,
    ]
    aliases: list[str] = []
    for raw in values:
        value = str(raw or "").strip().split("#", 1)[0]
        if not value:
            continue
        filename = value.rsplit("/", 1)[-1]
        stem = filename.rsplit(".", 1)[0]
        for alias in (value, filename, stem):
            if alias and alias not in aliases:
                aliases.append(alias)
    return aliases


def merged_locator_metadata(
    evidence_metadata: dict[str, Any],
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    derived = _selected_locator_metadata(items)
    metadata: dict[str, Any] = {
        key: values or _coerce_locator_values(evidence_metadata.get(key))
        for key, values in derived.items()
    }
    metadata["source_page_locators"] = _source_page_locators(items)
    return metadata


def _selected_locator_metadata(items: list[dict[str, Any]]) -> dict[str, list[str]]:
    return {
        "page_coverage": _unique_selected(_item_page_labels(item) for item in items),
        "source_ids": _unique_selected(_item_source_ids(item) for item in items),
        "evidence_ids": _unique_selected(
            [[str(item.get("evidence_id") or "").strip()] for item in items]
        ),
    }


def _source_page_locators(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    locators: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        pairs = {
            (
                str(item.get("source_id") or "").strip(),
                str(item.get("page_label") or "").strip(),
            )
        }
        for source_ref in item.get("source_backrefs") or []:
            value = str(source_ref or "")
            if "#page:" in value:
                source, page = value.split("#page:", 1)
                pairs.add((source.strip(), page.split("#", 1)[0].strip()))
        for source, page in pairs:
            if not source or not page or (source, page) in seen:
                continue
            seen.add((source, page))
            locators.append({"source_id": source, "page_label": page})
    return locators


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
