from __future__ import annotations

from typing import Any


def exact_alias_values(
    item: dict[str, Any],
    *,
    identity_key: str,
    identity_kind: str,
) -> set[str]:
    aliases = {identity_key}
    for key in ("runtime_identity", "evaluation_identity"):
        _add_alias(aliases, item.get(key))
        metadata = item.get("metadata")
        if isinstance(metadata, dict):
            _add_alias(aliases, metadata.get(key))
    canonical_id = str(item.get("canonical_id") or "").strip()
    if canonical_id == identity_key:
        aliases.add(canonical_id)
    if identity_kind == "cell":
        _add_alias(aliases, item.get("cell_id"))
        metadata = item.get("metadata")
        values = metadata.get("cell_id_aliases") if isinstance(metadata, dict) else ()
        for value in values or ():
            _add_alias(aliases, value)
    elif identity_kind == "span":
        _add_alias(aliases, item.get("span_id"))
        if not str(item.get("span_id") or "").strip():
            _add_alias(aliases, item.get("element_id"))
    elif identity_kind == "element":
        _add_alias(aliases, item.get("element_id"))
    elif identity_kind in {"evidence", "chunk"}:
        _add_alias(aliases, item.get("evidence_id"))
        aliases.update(
            str(value).strip()
            for value in item.get("duplicate_evidence_ids") or []
            if str(value).strip()
        )
    return aliases


def grouping_alias_values(
    item: dict[str, Any],
    *,
    exact_aliases: set[str],
) -> set[str]:
    return {
        value
        for value in (
            str(item.get("canonical_id") or "").strip(),
            str(item.get("element_id") or "").strip(),
            str(item.get("evidence_id") or "").strip(),
            str(item.get("parent_element_id") or "").strip(),
            str(item.get("table_id") or "").strip(),
            *(str(value).strip() for value in item.get("duplicate_evidence_ids") or []),
        )
        if value and value not in exact_aliases
    }


def _add_alias(aliases: set[str], value: Any) -> None:
    normalized = str(value or "").strip()
    if normalized:
        aliases.add(normalized)
