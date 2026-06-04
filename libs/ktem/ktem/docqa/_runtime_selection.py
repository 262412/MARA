from __future__ import annotations

from typing import Any, Optional


def normalize_selected_file_ids(selected_file_ids: Any) -> list[str]:
    if selected_file_ids in (None, ""):
        return []
    if isinstance(selected_file_ids, list):
        return [str(item) for item in selected_file_ids if item not in (None, "")]
    return [str(selected_file_ids)]


def normalize_page_number(page_number: Any) -> Optional[int]:
    if page_number in (None, ""):
        return None
    return max(1, int(page_number))


def normalize_qa_scope(qa_scope: Any, page_number: Any = None) -> str:
    value = str(qa_scope or "auto").strip().lower().replace("-", "_")
    if value in {"", "auto"}:
        return "page" if page_number not in (None, "") else "document"
    if value in {"doc", "whole_document", "full_document"}:
        return "document"
    if value in {"multi", "multi_doc", "multi_docs", "multi_document"}:
        return "multi_document"
    if value not in {"page", "document", "multi_document"}:
        raise ValueError(
            "Unknown QA scope '{}'. Expected page, document, multi-document, "
            "or auto.".format(qa_scope)
        )
    return value


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
        file_ids.extend(_selected_file_id_candidates(value))
    return merge_unique_file_ids(file_ids)


def resolve_file_refs(records: list[Any], refs: list[str]) -> list[Any]:
    if not refs:
        return records

    by_id = {str(record.file_id): record for record in records}
    by_name = _records_by_lower_name(records)
    resolved: list[Any] = []
    seen: set[str] = set()

    for ref in refs:
        match = _match_record(records, by_id, by_name, str(ref or "").strip())
        if match.file_id not in seen:
            seen.add(match.file_id)
            resolved.append(match)
    return resolved


def _selected_file_id_candidates(value: Any) -> list[str]:
    if (
        isinstance(value, list)
        and len(value) >= 3
        and str(value[0] or "").strip() in {"disabled", "select", "all"}
    ):
        candidates = [value[1]]
    else:
        candidates = value if isinstance(value, list) else [value]
    return _flatten_selected_candidates(candidates)


def _flatten_selected_candidates(candidates: list[Any]) -> list[str]:
    file_ids: list[str] = []
    for candidate in candidates:
        if isinstance(candidate, list):
            for nested in candidate:
                item = _selected_file_id(nested)
                if item:
                    file_ids.append(item)
        else:
            item = _selected_file_id(candidate)
            if item:
                file_ids.append(item)
    return file_ids


def _selected_file_id(candidate: Any) -> str:
    if isinstance(candidate, (dict, tuple, list)):
        return ""
    item = str(candidate or "").strip()
    return "" if item.lower() in {"select", "upload", "all"} else item


def _records_by_lower_name(records: list[Any]) -> dict[str, list[Any]]:
    by_name: dict[str, list[Any]] = {}
    for record in records:
        by_name.setdefault(str(record.name).lower(), []).append(record)
    return by_name


def _match_record(
    records: list[Any],
    by_id: dict[str, Any],
    by_name: dict[str, list[Any]],
    key: str,
) -> Any:
    if not key:
        raise ValueError("Unable to resolve empty file reference.")

    match = by_id.get(key)
    if match is not None:
        return match

    exact = by_name.get(key.lower(), [])
    if len(exact) == 1:
        return exact[0]
    if len(exact) > 1:
        raise ValueError(f"File reference '{key}' is ambiguous.")

    contains = [
        record
        for record in records
        if key.lower() in str(record.name).lower()
        or key.lower() in str(record.file_id).lower()
    ]
    if len(contains) == 1:
        return contains[0]
    if len(contains) > 1:
        raise ValueError(f"File reference '{key}' is ambiguous.")
    raise ValueError(f"Unable to resolve file reference '{key}'.")
