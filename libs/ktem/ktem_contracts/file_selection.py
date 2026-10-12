"""File ID selection semantics shared by DocQA and chat."""

from __future__ import annotations

from typing import Any


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
