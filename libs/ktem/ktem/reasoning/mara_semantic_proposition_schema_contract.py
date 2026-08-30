from __future__ import annotations

from collections.abc import Collection, Mapping
from itertools import combinations
from typing import Any

from ktem.docqa.question_proposition import PROPOSITION_EVIDENCE_SLOTS

from .mara_semantic_proposition_evidence_plan import (
    normalized_proposition_evidence_plans,
)


def semantic_proposition_schema(
    slot_ids: list[str],
    *,
    span_selectors: Collection[str] = (),
    candidate: str = "",
    applicable_proposition_slots: Collection[str] | None = None,
    allowed_proposition_slot_bindings: Mapping[str, Collection[str]] | None = None,
    allowed_proposition_evidence_plans: Mapping[str, Mapping[str, Any]] | None = None,
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
    selectors = tuple(dict.fromkeys(str(value) for value in span_selectors if value))
    allowed_bindings = _normalized_allowed_bindings(
        allowed_proposition_slot_bindings,
        proposition_slots,
    )
    allowed_plans = _normalized_allowed_plans(
        allowed_proposition_evidence_plans,
        allowed_bindings,
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
            selectors=selectors,
            allowed_bindings=allowed_bindings,
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
                selectors=selectors,
                allowed_bindings=allowed_bindings,
                allowed_plans=allowed_plans,
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
    selectors: tuple[str, ...],
    allowed_bindings: dict[str, tuple[str, ...]] | None,
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
            "items": _premise_schema(
                slot_ids,
                proposition_slots,
                selectors=selectors,
                allowed_bindings=allowed_bindings,
            ),
        },
        "unknown_assessment": _unknown_assessment_schema(
            proposition_slots,
            selectors=selectors,
        ),
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
        not_applicable = [
            slot for slot in PROPOSITION_EVIDENCE_SLOTS if slot not in proposition_slots
        ]
        properties["not_applicable_proposition_slots"] = {
            "type": "array",
            "enum": [not_applicable],
        }
    return properties


def _judgment_branch(
    slot_ids: list[str],
    judgment: str,
    unknown: bool,
    include_not_applicable: bool,
    proposition_slots: tuple[str, ...],
    *,
    selectors: tuple[str, ...],
    allowed_bindings: dict[str, tuple[str, ...]] | None,
    allowed_plans: dict[str, dict[str, Any]] | None,
    include_evidence_relation: bool,
    evidence_relations: Collection[str] | None = None,
) -> dict[str, Any]:
    properties = _proposition_properties(
        slot_ids,
        include_not_applicable,
        proposition_slots,
        selectors=selectors,
        allowed_bindings=allowed_bindings,
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
    properties["premises"] = _judgment_premises_schema(
        slot_ids,
        proposition_slots,
        unknown=unknown,
        selectors=selectors,
        allowed_bindings=allowed_bindings,
        allowed_plans=allowed_plans,
        evidence_relations=evidence_relations,
    )
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


def _judgment_premises_schema(
    slot_ids: list[str],
    proposition_slots: tuple[str, ...],
    *,
    unknown: bool,
    selectors: tuple[str, ...],
    allowed_bindings: dict[str, tuple[str, ...]] | None,
    allowed_plans: dict[str, dict[str, Any]] | None,
    evidence_relations: Collection[str] | None,
) -> dict[str, Any]:
    schema: dict[str, Any] = {
        "type": "array",
        "minItems": 0 if unknown else 1,
        "maxItems": 0 if unknown else 4,
        "items": _premise_schema(
            slot_ids,
            proposition_slots,
            selectors=selectors,
            allowed_bindings=allowed_bindings,
        ),
        **(
            {}
            if unknown
            else {
                "allOf": [
                    {
                        "contains": {
                            "type": "object",
                            "properties": {
                                "binds_proposition_slots": {
                                    "type": "array",
                                    "contains": {
                                        "type": "string",
                                        "enum": [slot],
                                    },
                                }
                            },
                            "required": ["binds_proposition_slots"],
                        }
                    }
                    for slot in proposition_slots
                ]
            }
        ),
    }
    if not unknown and allowed_plans is not None:
        eligible_plans = {
            plan_id: plan
            for plan_id, plan in allowed_plans.items()
            if str(plan["polarity_relation"]) in set(evidence_relations or ())
        }
        return _planned_premises_schema(
            slot_ids,
            proposition_slots,
            eligible_plans,
            allowed_bindings=allowed_bindings or {},
        )
    return schema


def _judgment_branches(
    slot_ids: list[str],
    *,
    candidate: str,
    include_not_applicable: bool,
    proposition_slots: tuple[str, ...],
    selectors: tuple[str, ...],
    allowed_bindings: dict[str, tuple[str, ...]] | None,
    allowed_plans: dict[str, dict[str, Any]] | None,
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
                selectors=selectors,
                allowed_bindings=allowed_bindings,
                allowed_plans=allowed_plans,
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
                selectors=selectors,
                allowed_bindings=allowed_bindings,
                allowed_plans=allowed_plans,
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
            selectors=selectors,
            allowed_bindings=allowed_bindings,
            allowed_plans=allowed_plans,
            include_evidence_relation=include_evidence_relation,
            evidence_relations=_candidate_judgment_relations(candidate, judgment),
        )
        for judgment in ("supported", "contradicted", "unknown")
    ]


def _premise_schema(
    slot_ids: list[str],
    proposition_slots: tuple[str, ...],
    *,
    selectors: tuple[str, ...],
    allowed_bindings: dict[str, tuple[str, ...]] | None,
) -> dict[str, Any]:
    base: dict[str, Any] = {
        "type": "object",
        "properties": {
            "span_selector": {
                "type": "string",
                "minLength": 1,
                "maxLength": 24,
                **({"enum": list(selectors)} if selectors else {}),
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
    if allowed_bindings is None:
        return base
    branches = []
    for selector, bound_slots in allowed_bindings.items():
        branch = {
            **base,
            "properties": {
                **base["properties"],
                "span_selector": {"type": "string", "enum": [selector]},
                "binds_proposition_slots": {
                    "type": "array",
                    "enum": [list(bound_slots)],
                },
            },
        }
        branches.append(branch)
    return {"oneOf": branches} if branches else {"not": {}}


def _planned_premises_schema(
    slot_ids: list[str],
    proposition_slots: tuple[str, ...],
    plans: Mapping[str, Mapping[str, Any]],
    *,
    allowed_bindings: dict[str, tuple[str, ...]],
) -> dict[str, Any]:
    branches: list[dict[str, Any]] = []
    for plan in plans.values():
        refs = tuple(str(ref) for ref in plan.get("span_refs") or ())
        plan_bindings = {
            ref: allowed_bindings[ref] for ref in refs if ref in allowed_bindings
        }
        if not refs or len(plan_bindings) != len(refs):
            continue
        branches.append(
            {
                "type": "array",
                "minItems": len(refs),
                "maxItems": len(refs),
                "items": _premise_schema(
                    slot_ids,
                    proposition_slots,
                    selectors=refs,
                    allowed_bindings=plan_bindings,
                ),
                "allOf": [
                    {
                        "contains": {
                            "type": "object",
                            "properties": {
                                "span_selector": {
                                    "type": "string",
                                    "enum": [ref],
                                }
                            },
                            "required": ["span_selector"],
                        }
                    }
                    for ref in refs
                ],
            }
        )
    return {"oneOf": branches} if branches else {"not": {}}


def _unknown_assessment_schema(
    proposition_slots: tuple[str, ...],
    *,
    selectors: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "reviewed_span_selectors": {
                "type": "array",
                "minItems": 1,
                "maxItems": 12,
                "items": {
                    "type": "string",
                    "maxLength": 24,
                    **({"enum": list(selectors)} if selectors else {}),
                },
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


def _normalized_allowed_bindings(
    value: Mapping[str, Collection[str]] | None,
    proposition_slots: tuple[str, ...],
) -> dict[str, tuple[str, ...]] | None:
    if value is None:
        return None
    allowed_slots = set(proposition_slots)
    normalized: dict[str, tuple[str, ...]] = {}
    for raw_selector, raw_slots in value.items():
        selector = str(raw_selector or "").strip()
        selected = tuple(
            slot
            for slot in PROPOSITION_EVIDENCE_SLOTS
            if slot in {str(value) for value in raw_slots} and slot in allowed_slots
        )
        if selector and selected:
            normalized[selector] = selected
    return normalized


def _normalized_allowed_plans(
    value: Mapping[str, Mapping[str, Any]] | None,
    allowed_bindings: dict[str, tuple[str, ...]] | None,
) -> dict[str, dict[str, Any]] | None:
    normalized = normalized_proposition_evidence_plans(value)
    if normalized is None:
        return None
    if allowed_bindings is None:
        return {}
    return {
        plan_id: plan
        for plan_id, plan in normalized.items()
        if set(plan["span_refs"]) <= set(allowed_bindings)
    }


def _candidate_judgment_relations(
    candidate: str,
    judgment: str,
) -> tuple[str, ...]:
    if judgment == "unknown":
        return ()
    if candidate == "yes":
        return (
            ("proposition_support",)
            if judgment == "supported"
            else ("explicit_contradiction",)
        )
    if candidate == "no":
        return (
            ("explicit_contradiction",)
            if judgment == "supported"
            else ("proposition_support",)
        )
    return ("proposition_support", "explicit_contradiction")
