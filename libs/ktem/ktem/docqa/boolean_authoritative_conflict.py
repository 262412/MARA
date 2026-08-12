from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .boolean_authority_schema import BooleanClaimAuthority, BooleanEvidenceAuthority
from .boolean_evidence_scope import evidence_item_text
from .evidence_identity import identity_of
from .query_phrase_extraction import source_page_locator

BOOLEAN_AUTHORITATIVE_CONFLICT_CONTRACT = "boolean_authoritative_conflict.v1"


def authoritative_conflict_claim(
    prompt: str,
    input_polarity: str,
    probe_polarity: str,
    supporting: tuple[BooleanEvidenceAuthority, ...],
    contradicting: tuple[BooleanEvidenceAuthority, ...],
) -> BooleanClaimAuthority:
    conflict = authoritative_conflict_payload((*supporting, *contradicting))
    if conflict is None:
        return BooleanClaimAuthority(
            claim=f"{probe_polarity}: {prompt}",
            status="unknown",
            input_answer_polarity=input_polarity,
            canonical_answer_polarity="",
            semantic_correction_applied=False,
            reason="internal_exact_span_polarity_inconsistency",
        )
    return BooleanClaimAuthority(
        claim=f"{probe_polarity}: {prompt}",
        status="conflicting",
        input_answer_polarity=input_polarity,
        canonical_answer_polarity="",
        semantic_correction_applied=False,
        supporting=supporting,
        contradicting=contradicting,
        reason="conflicting_exact_boolean_propositions",
        authoritative_conflict=conflict,
    )


def authoritative_conflict_payload(
    authorities: Iterable[BooleanEvidenceAuthority],
) -> dict[str, Any] | None:
    sides = {
        "yes": _deduplicated_authorities(
            authority for authority in authorities if authority.polarity == "yes"
        ),
        "no": _deduplicated_authorities(
            authority for authority in authorities if authority.polarity == "no"
        ),
    }
    positive = sides["yes"]
    negative = sides["no"]
    if (
        not positive
        or not negative
        or not authority_sides_are_disjoint(
            positive,
            negative,
        )
    ):
        return None
    return {
        "contract_id": BOOLEAN_AUTHORITATIVE_CONFLICT_CONTRACT,
        "status": "verified_conflict",
        "positive_authorities": positive,
        "negative_authorities": negative,
        "required_slot_ids": [],
        "verified_required_slot_ids": [],
        "required_evidence_ids": _authority_evidence_ids(positive, negative),
        "required_evidence_coverage": 0.0,
    }


def authority_atom_key(authority: dict[str, Any]) -> tuple[str, str]:
    return (
        str(authority.get("evidence_id") or "").strip(),
        str(authority.get("evidence_ref") or authority.get("span_id") or "").strip(),
    )


def authority_sides_are_disjoint(
    positive: Iterable[dict[str, Any]],
    negative: Iterable[dict[str, Any]],
) -> bool:
    positive_keys = {authority_atom_key(value) for value in positive}
    negative_keys = {authority_atom_key(value) for value in negative}
    return bool(
        positive_keys
        and negative_keys
        and all(all(key) for key in positive_keys | negative_keys)
        and positive_keys.isdisjoint(negative_keys)
    )


def conflict_authorities(conflict: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        dict(value)
        for field in ("positive_authorities", "negative_authorities")
        for value in conflict.get(field) or []
        if isinstance(value, dict)
    ]


def conflict_sides_are_complete(conflict: dict[str, Any]) -> bool:
    if conflict.get("contract_id") != BOOLEAN_AUTHORITATIVE_CONFLICT_CONTRACT:
        return False
    positive = _dict_values(conflict.get("positive_authorities"))
    negative = _dict_values(conflict.get("negative_authorities"))
    return bool(
        positive
        and negative
        and authority_sides_are_disjoint(positive, negative)
        and all(_authority_entry_complete(value, "yes") for value in positive)
        and all(_authority_entry_complete(value, "no") for value in negative)
    )


def authoritative_conflict_complete(conflict: dict[str, Any]) -> bool:
    required = _string_values(conflict.get("required_slot_ids"))
    verified = _string_values(conflict.get("verified_required_slot_ids"))
    try:
        coverage = float(str(conflict.get("required_evidence_coverage") or ""))
    except (TypeError, ValueError):
        return False
    return bool(
        conflict.get("status") == "verified_conflict"
        and conflict_sides_are_complete(conflict)
        and required
        and set(required) == set(verified)
        and coverage == 1.0
    )


def with_verified_conflict_slots(
    conflict: dict[str, Any],
    reconciled_slots: dict[str, tuple[str, ...]],
) -> dict[str, Any]:
    required_slot_ids = list(reconciled_slots)
    required_evidence_ids = list(
        dict.fromkeys(
            evidence_id
            for values in reconciled_slots.values()
            for evidence_id in values
        )
    )
    return {
        **conflict,
        "status": "verified_conflict",
        "required_slot_ids": required_slot_ids,
        "verified_required_slot_ids": required_slot_ids,
        "required_evidence_ids": required_evidence_ids,
        "required_evidence_coverage": 1.0 if required_slot_ids else 0.0,
    }


def conflict_authority_matches_item(
    authority: dict[str, Any],
    item: dict[str, Any],
) -> bool:
    try:
        identity = identity_of(item).key
    except ValueError:
        return False
    if str(authority.get("evidence_id") or "") != identity:
        return False
    evidence_ref = str(authority.get("evidence_ref") or "")
    span_id = str(authority.get("span_id") or "")
    if not evidence_ref or evidence_ref != span_id:
        return False
    quote = str(authority.get("quote") or "")
    start = authority.get("span_start")
    end = authority.get("span_end")
    text = evidence_item_text(item)
    if not (
        quote
        and isinstance(start, int)
        and isinstance(end, int)
        and 0 <= start < end
        and text[start:end] == quote
    ):
        return False
    source_id, page_label = source_page_locator(item)
    return bool(
        source_id
        and page_label
        and str(authority.get("source_id") or "") == source_id
        and str(authority.get("page_label") or "") == page_label
    )


def _deduplicated_authorities(
    authorities: Iterable[BooleanEvidenceAuthority],
) -> list[dict[str, Any]]:
    output: dict[tuple[str, str], dict[str, Any]] = {}
    for authority in authorities:
        payload = authority.as_dict()
        output.setdefault(authority_atom_key(payload), payload)
    return [output[key] for key in sorted(output)]


def _authority_entry_complete(value: dict[str, Any], polarity: str) -> bool:
    key = authority_atom_key(value)
    start = value.get("span_start")
    end = value.get("span_end")
    return bool(
        all(key)
        and value.get("evidence_ref") == value.get("span_id")
        and str(value.get("quote") or "").strip()
        and isinstance(start, int)
        and isinstance(end, int)
        and 0 <= start < end
        and value.get("polarity") == polarity
        and str(value.get("source_id") or "").strip()
        and str(value.get("page_label") or "").strip()
        and str(value.get("actor") or "").strip()
        and str(value.get("section_scope") or "").strip()
        and str(value.get("relation") or "").strip()
        and str(value.get("object") or "").strip()
        and str(value.get("qualifier") or "").strip()
        and str(value.get("quantifier") or "").strip()
    )


def _authority_evidence_ids(
    positive: list[dict[str, Any]],
    negative: list[dict[str, Any]],
) -> list[str]:
    return list(
        dict.fromkeys(
            str(value.get("evidence_id") or "")
            for value in [*positive, *negative]
            if str(value.get("evidence_id") or "")
        )
    )


def _dict_values(value: Any) -> list[dict[str, Any]]:
    values: Iterable[Any]
    if isinstance(value, dict):
        values = value.values()
    elif isinstance(value, (list, tuple)):
        values = value
    else:
        return []
    return [dict(item) for item in values if isinstance(item, dict)]


def _string_values(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple, set)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
