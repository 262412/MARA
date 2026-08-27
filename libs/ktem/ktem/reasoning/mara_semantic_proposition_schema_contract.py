from __future__ import annotations

from collections.abc import Collection
from itertools import combinations
from typing import Any

from ktem.docqa.question_proposition import PROPOSITION_EVIDENCE_SLOTS


def semantic_proposition_schema(
    slot_ids: list[str],
    *,
    candidate: str = "",
    applicable_proposition_slots: Collection[str] | None = None,
) -> dict[str, Any]:
    normalized_candidate = str(candidate or "").strip().casefold()
    include_not_applicable = applicable_proposition_slots is not None
    include_evidence_relation = normalized_candidate not in {"yes", "no"}
    requested_slots = (
        {str(slot) for slot in applicable_proposition_slots}
        if applicable_proposition_slots is not None
        else set(PROPOSITION_EVIDENCE_SLOTS)
    )
    proposition_slots = tuple(
        slot for slot in PROPOSITION_EVIDENCE_SLOTS if slot in requested_slots
    )
    required = [
        "candidate_judgment",
        "support_mode",
        "jointly_complete",
        "each_premise_required",
        "premises",
    ]
    if include_not_applicable:
        required.append("not_applicable_proposition_slots")
    return {
        "type": "object",
        "properties": _proposition_properties(
            slot_ids,
            include_not_applicable,
            proposition_slots,
            include_evidence_relation=include_evidence_relation,
        ),
        "required": required,
        "additionalProperties": False,
        "oneOf": [
            *_judgment_branches(
                slot_ids,
                candidate=normalized_candidate,
                include_not_applicable=include_not_applicable,
                proposition_slots=proposition_slots,
                include_evidence_relation=include_evidence_relation,
            ),
        ],
    }


def proposition_slot_scope(
    payload: Any,
    requested_applicable_slots: Collection[str] | None,
) -> tuple[set[str], set[str], str]:
    all_slots = set(PROPOSITION_EVIDENCE_SLOTS)
    raw_na = (
        payload.get("not_applicable_proposition_slots")
        if isinstance(payload, dict)
        else None
    )
    if requested_applicable_slots is None:
        if raw_na is None:
            return all_slots, set(), ""
        if not _valid_na(raw_na, all_slots):
            return set(), set(), "not_applicable_proposition_slots_invalid"
        not_applicable = set(raw_na)
        return all_slots - not_applicable, not_applicable, ""
    applicable = {str(slot) for slot in requested_applicable_slots}
    if not applicable or not applicable <= all_slots:
        return set(), set(), "not_applicable_proposition_slots_invalid"
    if raw_na is None and isinstance(payload, dict) and "verdict" in payload:
        return applicable, all_slots - applicable, ""
    if (
        not isinstance(raw_na, list)
        or not _valid_na(raw_na, all_slots)
        or set(raw_na) != all_slots - applicable
    ):
        return set(), set(), "not_applicable_proposition_slots_invalid"
    return applicable, all_slots - applicable, ""


def _valid_na(value: Any, all_slots: set[str]) -> bool:
    return bool(
        isinstance(value, list)
        and len(set(value)) == len(value)
        and all(slot in all_slots for slot in value)
    )


def _proposition_properties(
    slot_ids: list[str],
    include_not_applicable: bool,
    proposition_slots: tuple[str, ...],
    *,
    include_evidence_relation: bool,
) -> dict[str, Any]:
    properties = {
        "candidate_judgment": {
            "type": "string",
            "enum": ["supported", "contradicted", "unknown"],
        },
        "support_mode": {"type": "string", "enum": ["evidence_set"]},
        "jointly_complete": {"type": "boolean"},
        "each_premise_required": {"type": "boolean"},
        "premises": {
            "type": "array",
            "minItems": 0,
            "maxItems": 4,
            "items": _premise_schema(slot_ids, proposition_slots),
        },
        "unknown_assessment": _unknown_assessment_schema(proposition_slots),
    }
    if include_evidence_relation:
        properties["evidence_relation"] = {
            "type": "string",
            "enum": [
                "proposition_support",
                "explicit_contradiction",
                "undetermined",
            ],
        }
    if include_not_applicable:
        properties["not_applicable_proposition_slots"] = {
            "type": "array",
            "maxItems": len(PROPOSITION_EVIDENCE_SLOTS),
            "items": {"type": "string", "enum": list(PROPOSITION_EVIDENCE_SLOTS)},
        }
    return properties


def _judgment_branch(
    slot_ids: list[str],
    judgment: str,
    unknown: bool,
    include_not_applicable: bool,
    proposition_slots: tuple[str, ...],
    *,
    include_evidence_relation: bool,
    evidence_relations: Collection[str] | None = None,
) -> dict[str, Any]:
    properties = _proposition_properties(
        slot_ids,
        include_not_applicable,
        proposition_slots,
        include_evidence_relation=include_evidence_relation,
    )
    properties["candidate_judgment"] = {"type": "string", "enum": [judgment]}
    if include_evidence_relation:
        properties["evidence_relation"] = {
            "type": "string",
            "enum": (
                ["undetermined"]
                if unknown
                else list(
                    evidence_relations
                    or ("proposition_support", "explicit_contradiction")
                )
            ),
        }
    flag = not unknown
    properties["jointly_complete"] = {"type": "boolean", "enum": [flag]}
    properties["each_premise_required"] = {"type": "boolean", "enum": [flag]}
    properties["premises"] = {
        "type": "array",
        "minItems": 0 if unknown else 1,
        "maxItems": 0 if unknown else 4,
        "items": _premise_schema(slot_ids, proposition_slots),
    }
    required = [
        "candidate_judgment",
        "support_mode",
        "jointly_complete",
        "each_premise_required",
        "premises",
    ]
    if include_evidence_relation:
        required.append("evidence_relation")
    if include_not_applicable:
        required.append("not_applicable_proposition_slots")
    if unknown:
        required.append("unknown_assessment")
    else:
        properties.pop("unknown_assessment")
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def _judgment_branches(
    slot_ids: list[str],
    *,
    candidate: str,
    include_not_applicable: bool,
    proposition_slots: tuple[str, ...],
    include_evidence_relation: bool,
) -> list[dict[str, Any]]:
    if candidate == "unanswerable":
        return [
            _judgment_branch(
                slot_ids,
                "contradicted",
                False,
                include_not_applicable,
                proposition_slots,
                include_evidence_relation=True,
                evidence_relations=(
                    "proposition_support",
                    "explicit_contradiction",
                ),
            ),
            _judgment_branch(
                slot_ids,
                "unknown",
                True,
                include_not_applicable,
                proposition_slots,
                include_evidence_relation=False,
            ),
        ]
    return [
        _judgment_branch(
            slot_ids,
            judgment,
            judgment == "unknown",
            include_not_applicable,
            proposition_slots,
            include_evidence_relation=include_evidence_relation,
        )
        for judgment in ("supported", "contradicted", "unknown")
    ]


def _premise_schema(
    slot_ids: list[str],
    proposition_slots: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "span_selector": {
                "type": "string",
                "minLength": 1,
                "maxLength": 24,
            },
            "proposition_fragment": {
                "type": "string",
                "minLength": 1,
                "maxLength": 320,
            },
            "supports_slot_ids": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "enum": slot_ids},
            },
            "binds_proposition_slots": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string", "enum": list(proposition_slots)},
            },
        },
        "required": [
            "span_selector",
            "proposition_fragment",
            "supports_slot_ids",
            "binds_proposition_slots",
        ],
        "additionalProperties": False,
    }


def _unknown_assessment_schema(
    proposition_slots: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "reviewed_span_selectors": {
                "type": "array",
                "minItems": 1,
                "maxItems": 12,
                "items": {"type": "string", "maxLength": 24},
            },
            "unresolved_proposition_slots": {
                "type": "string",
                "enum": _canonical_slot_sets(proposition_slots),
            },
            "support_gap": {
                "type": "string",
                "minLength": 1,
                "maxLength": 320,
            },
            "contradiction_gap": {
                "type": "string",
                "minLength": 1,
                "maxLength": 320,
            },
        },
        "required": [
            "reviewed_span_selectors",
            "unresolved_proposition_slots",
            "support_gap",
            "contradiction_gap",
        ],
        "additionalProperties": False,
    }


def _canonical_slot_sets(proposition_slots: tuple[str, ...]) -> list[str]:
    """Encode a non-empty unique slot set without unsupported ``uniqueItems``."""

    return [
        "|".join(selected)
        for count in range(1, len(proposition_slots) + 1)
        for selected in combinations(proposition_slots, count)
    ]
