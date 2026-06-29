from __future__ import annotations

from typing import Any, Iterable


def normalize_selected_file_ids(selected_file_ids: Any) -> list[str]:
    if selected_file_ids in (None, ""):
        return []
    if isinstance(selected_file_ids, list):
        return [str(item) for item in selected_file_ids if item not in (None, "")]
    return [str(selected_file_ids)]


def merge_unique_file_ids(*groups: Any) -> list[str]:
    merged: list[str] = []
    seen = set()
    for group in groups:
        if group in (None, ""):
            continue
        values = group if isinstance(group, list) else [group]
        for value in values:
            item = str(value or "").strip()
            if not item or item in seen:
                continue
            seen.add(item)
            merged.append(item)
    return merged


def extract_selected_ids_from_data_source(data_source: dict | None) -> list[str]:
    if not isinstance(data_source, dict):
        return []

    selected = data_source.get("selected", {})
    if not isinstance(selected, dict):
        return []

    file_ids: list[str] = []
    for value in selected.values():
        candidates = _selected_value_candidates(value)
        for candidate in candidates:
            file_ids.extend(_candidate_file_ids(candidate))
    return merge_unique_file_ids(file_ids)


def build_selected_input_map(
    indices: Iterable[Any],
    selecteds: tuple[Any, ...],
) -> dict[int, object]:
    selected_inputs: dict[int, object] = {}
    for index in indices:
        selector = getattr(index, "selector", None)
        if selector is None:
            continue
        if isinstance(selector, int) and selector < len(selecteds):
            selected_inputs[index.id] = selecteds[selector]
        elif isinstance(selector, tuple):
            selected_inputs[index.id] = [
                selecteds[i] for i in selector if i < len(selecteds)
            ]
    return selected_inputs


def is_group_selector_value(selector_value: str) -> bool:
    value = str(selector_value or "").strip()
    return value.startswith("[") and value.endswith("]")


def build_selector_source_map(first_selector_choices: Any) -> dict[str, str]:
    source_map: dict[str, str] = {}
    for item in list(first_selector_choices or []):
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        name = str(item[0] or "")
        file_id = str(item[1] or "")
        if not file_id or is_group_selector_value(file_id):
            continue
        source_map[file_id] = name or file_id
    return source_map


def sync_graph_source_ids(
    graph_source_ids: Any,
    available_source_map: dict[str, str],
    selector_source_map: dict[str, str],
) -> list[str]:
    current_ids = normalize_selected_file_ids(graph_source_ids)
    if not current_ids:
        return []

    source_map = available_source_map or selector_source_map
    if not source_map:
        return current_ids

    available_ids = set(source_map.keys())
    return [file_id for file_id in current_ids if file_id in available_ids]


def _selected_value_candidates(value: Any) -> list[Any]:
    if (
        isinstance(value, list)
        and len(value) >= 3
        and str(value[0] or "").strip() in {"disabled", "select", "all"}
    ):
        return [value[1]]
    return value if isinstance(value, list) else [value]


def _candidate_file_ids(candidate: Any) -> list[str]:
    if isinstance(candidate, list):
        return [
            item
            for nested in candidate
            if not isinstance(nested, (dict, tuple, list))
            for item in [_clean_file_id(nested)]
            if item
        ]
    if isinstance(candidate, (dict, tuple)):
        return []
    item = _clean_file_id(candidate)
    return [item] if item else []


def _clean_file_id(value: Any) -> str:
    item = str(value or "").strip()
    if not item or item.lower() in {"select", "upload", "all"}:
        return ""
    return item
