from __future__ import annotations

from typing import Any

from .evidence_identity import identity_of
from .retrieval_semantic_identity import semantic_retrieval_identity


def merge_retrieval_metadata(
    first: dict[str, Any],
    second: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(first)
    for key, value in second.items():
        current = merged.get(key)
        if isinstance(current, list) and isinstance(value, list):
            merged[key] = _stable_union(current, value)
        elif isinstance(current, dict) and isinstance(value, dict):
            merged[key] = {**current, **value}
        elif value not in (None, "", [], {}):
            merged[key] = value
    return merged


def _stable_union(first: list[Any], second: list[Any]) -> list[Any]:
    output: list[Any] = []
    identities: set[str] = set()
    for item in [*first, *second]:
        identity = _retrieval_value_identity(item)
        if identity in identities:
            existing_index = next(
                index
                for index, existing in enumerate(output)
                if _retrieval_value_identity(existing) == identity
            )
            output[existing_index] = _merge_retrieval_value(
                output[existing_index],
                item,
            )
            continue
        identities.add(identity)
        output.append(item)
    return output


def _retrieval_value_identity(value: Any) -> str:
    if not isinstance(value, dict):
        return repr(value)
    semantic_identity = semantic_retrieval_identity(value)
    if semantic_identity is not None:
        return semantic_identity
    try:
        return identity_of(value).key
    except ValueError:
        return repr(sorted(value.items()))


def _merge_retrieval_value(left: Any, right: Any) -> Any:
    if not isinstance(left, dict) or not isinstance(right, dict):
        return left
    merged = dict(left)
    merged["retrieval_lineage"] = _stable_dict_union(
        list(left.get("retrieval_lineage") or []),
        list(right.get("retrieval_lineage") or []),
    )
    merged["source_backrefs"] = list(
        dict.fromkeys(
            [
                *list(left.get("source_backrefs") or []),
                *list(right.get("source_backrefs") or []),
            ]
        )
    )
    metadata = dict(left.get("metadata") or {})
    for key, value in dict(right.get("metadata") or {}).items():
        if key not in metadata:
            metadata[key] = value
    if metadata:
        merged["metadata"] = metadata
    return merged


def _stable_dict_union(
    first: list[dict[str, Any]],
    second: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    for item in [*first, *second]:
        key = tuple(sorted((str(name), str(value)) for name, value in item.items()))
        if key in seen:
            continue
        seen.add(key)
        output.append(item)
    return output
