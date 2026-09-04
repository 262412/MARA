from __future__ import annotations

from typing import Any

from .evidence_identity import identity_of
from .visual_evidence_authority import (
    TYPED_VISUAL_EVIDENCE_PATH_CONTRACT,
    _is_typed_visual_item,
    _unique_strings,
)

VISUAL_FINAL_BINDING_PROJECTION_CONTRACT = "visual_final_binding_projection.v1"


def final_visual_binding_projection(
    bundle: Any,
    decision: Any,
    request: Any | None = None,
) -> dict[str, Any] | None:
    """Project verified visual bindings for final and terminal consumers."""

    if getattr(decision, "status", "") != "supported":
        return None
    authority = getattr(decision, "typed_authority", None)
    if (
        not isinstance(authority, dict)
        or authority.get("contract_id") != TYPED_VISUAL_EVIDENCE_PATH_CONTRACT
        or authority.get("state") != "verified_support"
    ):
        return None
    required = _unique_strings(authority.get("required_slot_ids"))
    verified = _unique_strings(authority.get("verified_support_slot_ids"))
    bindings = _validated_bindings(bundle, authority, required)
    if bindings is None or set(required) != set(verified):
        return None
    normalized, items = bindings
    state_version = authority.get("query_plan_state_version")
    if state_version is None:
        state_version = (
            getattr(request, "query_plan_state_version", 0) if request else 0
        )
    return {
        "contract_id": VISUAL_FINAL_BINDING_PROJECTION_CONTRACT,
        "stage": "final",
        "status": "verified_support",
        "required_slot_ids": required,
        "verified_support_slot_ids": verified,
        "slot_bindings": normalized,
        "evidence_ids": [
            evidence_id for values in normalized.values() for evidence_id in values
        ],
        "source_page_locators": _source_page_locators(items),
        "verified_slot_coverage": 1.0,
        "query_plan_state_version": int(state_version or 0),
        "preserves_selection_trace": True,
        "selection_trace_stage": "selection",
    }


def _validated_bindings(
    bundle: Any,
    authority: dict[str, Any],
    required: list[str],
) -> tuple[dict[str, list[str]], list[dict[str, Any]]] | None:
    bindings = authority.get("slot_bindings")
    if not required or not isinstance(bindings, dict) or set(bindings) != set(required):
        return None
    lookup = _typed_item_lookup(bundle)
    normalized: dict[str, list[str]] = {}
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for slot_id in required:
        evidence_ids = _unique_strings(bindings.get(slot_id))
        if not evidence_ids or any(
            evidence_id not in lookup for evidence_id in evidence_ids
        ):
            return None
        normalized[slot_id] = evidence_ids
        for evidence_id in evidence_ids:
            item = lookup[evidence_id]
            item_identity = _item_identity(item, evidence_id)
            if item_identity not in seen:
                seen.add(item_identity)
                items.append(item)
    return normalized, items


def _typed_item_lookup(bundle: Any) -> dict[str, dict[str, Any]]:
    lookup: dict[str, dict[str, Any]] = {}
    for item in getattr(bundle, "items", []) or []:
        if not isinstance(item, dict) or not _is_typed_visual_item(item):
            continue
        try:
            identity = identity_of(item).key
        except ValueError:
            identity = ""
        if identity:
            lookup.setdefault(identity, item)
        evidence_id = str(item.get("evidence_id") or "").strip()
        if evidence_id:
            lookup.setdefault(evidence_id, item)
    return lookup


def _item_identity(item: dict[str, Any], fallback: str) -> str:
    try:
        return identity_of(item).key or fallback
    except ValueError:
        return fallback


def _source_page_locators(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    locators: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in items:
        metadata = dict(item.get("metadata") or {})
        source_id = str(
            item.get("source_id")
            or item.get("file_id")
            or item.get("document_id")
            or metadata.get("source_id")
            or metadata.get("file_id")
            or ""
        ).strip()
        page_label = str(
            item.get("page_label")
            or item.get("page")
            or item.get("page_number")
            or metadata.get("page_label")
            or metadata.get("page")
            or ""
        ).strip()
        if not source_id or not page_label or (source_id, page_label) in seen:
            continue
        seen.add((source_id, page_label))
        locators.append({"source_id": source_id, "page_label": page_label})
    return locators
