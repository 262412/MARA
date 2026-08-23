from __future__ import annotations

from typing import Any

from ktem.docqa.query_evidence_binding_support import candidate_score_for_slot


def slot_values(slot: Any, key: str) -> tuple[str, ...]:
    values = (
        slot.get(key, []) if isinstance(slot, dict) else getattr(slot, key, ()) or ()
    )
    return tuple(
        dict.fromkeys(str(value).strip() for value in values if str(value).strip())
    )


def matching_slot_ids(slots: list[dict[str, Any]], evidence_id: str) -> tuple[str, ...]:
    return tuple(
        slot["slot_id"]
        for slot in slots
        if evidence_id in slot_values(slot, "evidence_ids")
    )


def evidence_refs(item: dict[str, Any]) -> tuple[str, ...]:
    metadata = item.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    values: list[str] = []
    for field in ("evidence_ref", "span_id", "canonical_ref", "reference"):
        for container in (item, metadata):
            value = container.get(field)
            if isinstance(value, (list, tuple, set)):
                values.extend(str(entry).strip() for entry in value)
            elif str(value or "").strip():
                values.append(str(value).strip())
    return tuple(dict.fromkeys(value for value in values if value))


def stable_source_id(item: dict[str, Any]) -> str:
    metadata = item.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    for key in (
        "evaluation_source_id",
        "canonical_document_id",
        "canonical_dataset_id",
        "document_id",
    ):
        for container in (item, metadata):
            value = str(container.get(key) or "").strip()
            if value:
                return value
    return ""


def evidence_alignment_score(request: Any, item: dict[str, Any]) -> float:
    plan = getattr(request, "query_plan", None)
    raw_slots = (
        plan.get("evidence_slots", [])
        if isinstance(plan, dict)
        else getattr(plan, "evidence_slots", ()) or ()
    )
    return max(
        (
            float(candidate_score_for_slot(slot, item, requires_structure=False))
            for slot in raw_slots
            if not isinstance(slot, dict)
            and str(getattr(slot, "statement_kind", "") or "").strip()
            == "boolean_proposition"
        ),
        default=0.0,
    )
