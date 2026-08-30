from __future__ import annotations

from collections.abc import Collection, Mapping
from typing import Any

from ktem.docqa.boolean_authority_schema import (
    GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
    SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
)
from ktem.docqa.question_proposition import PROPOSITION_EVIDENCE_SLOTS

from .mara_semantic_proposition_evidence_plan import (
    candidate_projection,
    canonical_premise_metadata,
    normalized_proposition_evidence_plans,
    verdict_for_evidence_relation,
)

_JUDGMENTS = ("supported", "contradicted", "unknown")


def canonical_plan_selection_contract(
    candidate: str,
    *,
    applicable_proposition_slots: Collection[str] | None,
    allowed_proposition_slot_bindings: Mapping[str, Collection[str]] | None,
    allowed_proposition_evidence_plans: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    requested_slots = (
        None
        if applicable_proposition_slots is None
        else {str(value) for value in applicable_proposition_slots}
    )
    proposition_slots = tuple(
        slot
        for slot in PROPOSITION_EVIDENCE_SLOTS
        if requested_slots is None or slot in requested_slots
    )
    allowed_bindings = normalized_proposition_slot_bindings(
        allowed_proposition_slot_bindings,
        proposition_slots,
    )
    allowed_plans = normalized_proposition_evidence_plan_choices(
        allowed_proposition_evidence_plans,
        allowed_bindings,
    )
    return canonical_plan_selection_schema(candidate, allowed_plans or {})


def normalized_proposition_slot_bindings(
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


def normalized_proposition_evidence_plan_choices(
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


def canonical_plan_selection_schema(
    candidate: str,
    allowed_plans: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    plans = normalized_proposition_evidence_plans(allowed_plans) or {}
    branches = []
    for judgment in ("supported", "contradicted"):
        plan_ids = [
            plan_id
            for plan_id, plan in plans.items()
            if candidate_judgment_matches_plan(
                candidate,
                judgment,
                str(plan["polarity_relation"]),
            )
        ]
        if plan_ids:
            branches.append(_selection_branch(judgment, plan_ids))
    if not plans:
        branches.append(_selection_branch("unknown", [""]))
    return {
        "type": "object",
        "properties": {
            "candidate_judgment": {
                "type": "string",
                "enum": list(_JUDGMENTS),
            },
            "canonical_evidence_plan_id": {
                "type": "string",
                "enum": ["", *plans],
            },
        },
        "required": ["candidate_judgment", "canonical_evidence_plan_id"],
        "additionalProperties": False,
        "oneOf": branches,
    }


def project_canonical_plan_selection(
    payload: Any,
    *,
    packed: list[dict[str, Any]],
    slot_ids: set[str],
    model: str,
    seed: int,
    candidate: str,
    applicable_proposition_slots: Collection[str] | None,
    allowed_proposition_slot_bindings: Mapping[str, Collection[str]] | None,
    slot_evidence_refs: Mapping[str, Collection[str]] | None,
    allowed_proposition_evidence_plans: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, Any] | None, str]:
    if not isinstance(payload, dict) or set(payload) != {
        "candidate_judgment",
        "canonical_evidence_plan_id",
    }:
        return None, "plan_selection_schema_invalid"
    judgment = payload.get("candidate_judgment")
    plan_id = payload.get("canonical_evidence_plan_id")
    if judgment not in _JUDGMENTS or not isinstance(plan_id, str):
        return None, "plan_selection_schema_invalid"
    applicable_slots = _applicable_slots(applicable_proposition_slots)
    if applicable_slots is None:
        return None, "canonical_evidence_plan_binding_invalid"
    plans = (
        normalized_proposition_evidence_plans(allowed_proposition_evidence_plans) or {}
    )
    if judgment == "unknown":
        if plan_id or plans:
            return None, "candidate_judgment_plan_mismatch"
        return (
            _unknown_value(
                packed,
                applicable_slots=applicable_slots,
                model=model,
                seed=seed,
            ),
            "",
        )
    if not plan_id:
        return None, "canonical_evidence_plan_id_invalid"
    plan = plans.get(plan_id)
    if plan is None:
        return None, "canonical_evidence_plan_id_invalid"
    relation = str(plan["polarity_relation"])
    if not candidate_judgment_matches_plan(candidate, str(judgment), relation):
        return None, "candidate_judgment_plan_mismatch"
    premises, reason = _project_plan_premises(
        plan,
        packed=packed,
        slot_ids=slot_ids,
        applicable_slots=applicable_slots,
        allowed_proposition_slot_bindings=allowed_proposition_slot_bindings,
        slot_evidence_refs=slot_evidence_refs,
    )
    if premises is None:
        return None, reason
    return (
        _bound_value(
            judgment=str(judgment),
            plan_id=plan_id,
            relation=relation,
            premises=premises,
            applicable_slots=applicable_slots,
            model=model,
            seed=seed,
        ),
        "",
    )


def candidate_judgment_matches_plan(
    candidate: str,
    judgment: str,
    relation: str,
) -> bool:
    candidate = str(candidate or "").strip().casefold()
    if judgment not in {"supported", "contradicted"}:
        return False
    if candidate in {"yes", "no"}:
        expected_relation, _ = candidate_projection(candidate, judgment)
        return relation == expected_relation
    if candidate == "unanswerable":
        return judgment == "contradicted" and relation in {
            "proposition_support",
            "explicit_contradiction",
        }
    return relation in {"proposition_support", "explicit_contradiction"}


def _selection_branch(judgment: str, plan_ids: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "candidate_judgment": {"type": "string", "enum": [judgment]},
            "canonical_evidence_plan_id": {
                "type": "string",
                "enum": plan_ids,
            },
        },
        "required": ["candidate_judgment", "canonical_evidence_plan_id"],
        "additionalProperties": False,
    }


def _project_plan_premises(
    plan: Mapping[str, Any],
    *,
    packed: list[dict[str, Any]],
    slot_ids: set[str],
    applicable_slots: tuple[str, ...],
    allowed_proposition_slot_bindings: Mapping[str, Collection[str]] | None,
    slot_evidence_refs: Mapping[str, Collection[str]] | None,
) -> tuple[list[dict[str, Any]] | None, str]:
    refs = tuple(str(ref) for ref in plan.get("span_refs") or ())
    slot_refs = _normalized_slot_refs(plan.get("slot_refs"), refs)
    if slot_refs is None or set(slot_refs) != set(applicable_slots):
        return None, "canonical_evidence_plan_binding_invalid"
    selector_lookup = {
        str(selector.get("selector_id") or ""): {
            "evidence_id": str(record.get("evidence_id") or ""),
            **selector,
        }
        for record in packed
        for selector in record.get("selectors") or []
        if isinstance(selector, dict) and str(selector.get("selector_id") or "")
    }
    if any(ref not in selector_lookup for ref in refs):
        return None, "canonical_evidence_plan_span_invalid"
    bindings = {
        ref: tuple(slot for slot in applicable_slots if ref in slot_refs[slot])
        for ref in refs
    }
    if any(not bound_slots for bound_slots in bindings.values()):
        return None, "canonical_evidence_plan_binding_invalid"
    if allowed_proposition_slot_bindings is not None and any(
        bindings[ref]
        != tuple(
            slot
            for slot in PROPOSITION_EVIDENCE_SLOTS
            if slot in set(allowed_proposition_slot_bindings.get(ref, ()))
        )
        for ref in refs
    ):
        return None, "canonical_evidence_plan_binding_invalid"
    if slot_evidence_refs is None or set(slot_evidence_refs) != slot_ids:
        return None, "canonical_evidence_plan_slot_invalid"
    supports_by_ref = {
        ref: sorted(
            slot_id
            for slot_id in slot_ids
            if ref in {str(value) for value in slot_evidence_refs[slot_id]}
        )
        for ref in refs
    }
    if any(not supports for supports in supports_by_ref.values()) or any(
        not any(slot_id in supports for supports in supports_by_ref.values())
        for slot_id in slot_ids
    ):
        return None, "canonical_evidence_plan_slot_invalid"
    premises: list[dict[str, Any]] = []
    for ref in refs:
        selector = selector_lookup[ref]
        text = str(selector.get("text") or "")
        if not text:
            return None, "canonical_evidence_plan_span_invalid"
        premises.append(
            {
                "evidence_id": str(selector["evidence_id"]),
                "span_selector": ref,
                "quote": text,
                "span_start": int(selector.get("span_start") or 0),
                "span_end": int(selector.get("span_end") or 0),
                "canonical_start": selector.get("canonical_start"),
                "canonical_end": selector.get("canonical_end"),
                "proposition_fragment": text,
                "supports_slot_ids": list(supports_by_ref[ref]),
                "binds_proposition_slots": list(bindings[ref]),
                **canonical_premise_metadata(selector),
            }
        )
    return premises, ""


def _normalized_slot_refs(
    value: Any,
    span_refs: tuple[str, ...],
) -> dict[str, tuple[str, ...]] | None:
    if not isinstance(value, Mapping):
        return None
    allowed_refs = set(span_refs)
    normalized: dict[str, tuple[str, ...]] = {}
    for raw_slot, raw_refs in value.items():
        slot = str(raw_slot or "")
        if (
            slot not in PROPOSITION_EVIDENCE_SLOTS
            or not isinstance(raw_refs, Collection)
            or isinstance(raw_refs, (str, bytes))
        ):
            return None
        refs = tuple(str(ref) for ref in raw_refs)
        if not refs or len(set(refs)) != len(refs) or not set(refs) <= allowed_refs:
            return None
        normalized[slot] = refs
    return normalized


def _applicable_slots(value: Collection[str] | None) -> tuple[str, ...] | None:
    requested = (
        set(PROPOSITION_EVIDENCE_SLOTS)
        if value is None
        else {str(slot) for slot in value}
    )
    slots = tuple(slot for slot in PROPOSITION_EVIDENCE_SLOTS if slot in requested)
    return slots if slots and set(slots) == requested else None


def _bound_value(
    *,
    judgment: str,
    plan_id: str,
    relation: str,
    premises: list[dict[str, Any]],
    applicable_slots: tuple[str, ...],
    model: str,
    seed: int,
) -> dict[str, Any]:
    return {
        "contract_id": SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
        "candidate_judgment": judgment,
        "verdict": verdict_for_evidence_relation(relation),
        "evidence_relation": relation,
        "support_mode": "evidence_set",
        "proof_mode": (
            "atomic_semantic" if len(premises) == 1 else "composite_conjunction"
        ),
        "jointly_complete": True,
        "each_premise_required": True,
        "premises": premises,
        "not_applicable_proposition_slots": [
            slot for slot in PROPOSITION_EVIDENCE_SLOTS if slot not in applicable_slots
        ],
        "canonical_evidence_plan_id": plan_id,
        "verifier": {
            "contract_id": GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
            "model": model,
            "seed": seed,
        },
    }


def _unknown_value(
    packed: list[dict[str, Any]],
    *,
    applicable_slots: tuple[str, ...],
    model: str,
    seed: int,
) -> dict[str, Any]:
    selector_lookup = {
        str(selector.get("selector_id") or ""): {
            "evidence_id": str(record.get("evidence_id") or ""),
            **selector,
        }
        for record in packed
        for selector in record.get("selectors") or []
        if isinstance(selector, dict) and str(selector.get("selector_id") or "")
    }
    reviewed_selectors = list(selector_lookup)[:12]
    reviewed = [
        {
            "span_selector": selector_id,
            "evidence_id": str(selector_lookup[selector_id]["evidence_id"]),
            "quote": str(selector_lookup[selector_id].get("text") or ""),
            "span_start": int(selector_lookup[selector_id].get("span_start") or 0),
            "span_end": int(selector_lookup[selector_id].get("span_end") or 0),
        }
        for selector_id in reviewed_selectors
    ]
    return {
        "contract_id": SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
        "candidate_judgment": "unknown",
        "verdict": "insufficient_evidence",
        "evidence_relation": "undetermined",
        "support_mode": "evidence_set",
        "proof_mode": "none",
        "jointly_complete": False,
        "each_premise_required": False,
        "premises": [],
        "not_applicable_proposition_slots": [
            slot for slot in PROPOSITION_EVIDENCE_SLOTS if slot not in applicable_slots
        ],
        "canonical_evidence_plan_id": "",
        "unknown_assessment": {
            "reviewed_span_selectors": reviewed_selectors,
            "reviewed_evidence": reviewed,
            "unresolved_proposition_slots": list(applicable_slots),
            "support_gap": (
                "No frozen canonical support plan establishes all applicable "
                "proposition slots."
            ),
            "contradiction_gap": (
                "No frozen canonical contradiction plan establishes all "
                "applicable proposition slots."
            ),
        },
        "verifier": {
            "contract_id": GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
            "model": model,
            "seed": seed,
        },
    }
