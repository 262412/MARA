from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from ktem.reasoning.mara_qasper_semantic_pack import qasper_canonical_selector_bindings
from ktem.reasoning.mara_semantic_proposition_plan_selection import (
    project_canonical_plan_selection,
)

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest

_BOUND_PLAN_KEYS = {
    "relation_bound_support": "support_plan",
    "relation_bound_contradiction": "contradiction_plan",
}


def projected_plan_authority_stage_payload(
    pack: Mapping[str, Any],
    generator: Mapping[str, Any],
    proposal_value: Mapping[str, Any],
) -> dict[str, Any]:
    binding = _mapping(pack.get("proposition_binding"))
    records = _mapping_list(pack.get("records"))
    slots = _mapping_list(pack.get("slots"))
    selection = {
        "candidate_judgment": str(proposal_value.get("candidate_judgment") or ""),
        "canonical_evidence_plan_id": str(
            proposal_value.get("canonical_evidence_plan_id") or ""
        ),
    }
    selected_plan_id = selection["canonical_evidence_plan_id"]
    plans = _frozen_evidence_plans(binding)
    projection, reason = _local_projection(
        selection,
        records=records,
        slots=slots,
        binding=binding,
        plans=plans,
        candidate=str(generator.get("typed_candidate") or ""),
    )
    premises = deepcopy(_mapping(projection).get("premises") or [])
    selected_plan = deepcopy(_mapping(plans.get(selected_plan_id)))
    slot_bindings = deepcopy(_mapping(selected_plan.get("slot_refs")))
    reasons = [reason] if reason else []
    return _payload(
        reasons,
        projection_authority_source="frozen_canonical_semantic_pack",
        projection_status="projected" if projection is not None else "not_projected",
        projection_reason=(
            reason or ("" if projection is not None else "selected_plan_unavailable")
        ),
        selection_input=selection,
        selection_input_digest=canonical_digest(selection),
        selected_plan_id=selected_plan_id,
        selected_plan=selected_plan,
        selected_plan_digest=canonical_digest(selected_plan),
        premises=premises,
        premises_digest=canonical_digest(premises),
        slot_bindings=slot_bindings,
        slot_bindings_digest=canonical_digest(slot_bindings),
        proof_mode=str(_mapping(projection).get("proof_mode") or ""),
        evidence_relation=str(_mapping(projection).get("evidence_relation") or ""),
    )


def _local_projection(
    selection: Mapping[str, str],
    *,
    records: list[dict[str, Any]],
    slots: list[dict[str, Any]],
    binding: Mapping[str, Any],
    plans: Mapping[str, Mapping[str, Any]],
    candidate: str,
) -> tuple[dict[str, Any] | None, str]:
    selected_plan_id = str(selection.get("canonical_evidence_plan_id") or "")
    if not selected_plan_id:
        return None, ""
    return project_canonical_plan_selection(
        dict(selection),
        packed=records,
        slot_ids={str(slot.get("slot_id") or "") for slot in slots},
        model="causal-transaction-local-projection",
        seed=0,
        candidate=candidate,
        applicable_proposition_slots=tuple(binding.get("applicable_slots") or ()),
        allowed_proposition_slot_bindings=qasper_canonical_selector_bindings(records),
        slot_evidence_refs={
            str(slot.get("slot_id") or ""): tuple(
                str(ref) for ref in slot.get("evidence_refs") or ()
            )
            for slot in slots
            if str(slot.get("slot_id") or "")
        },
        allowed_proposition_evidence_plans=plans,
    )


def _frozen_evidence_plans(
    binding: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    plan = _mapping(binding.get("canonical_evidence_plan"))
    selected_key = _BOUND_PLAN_KEYS.get(str(binding.get("binding_state") or ""))
    selected = _mapping(plan.get(selected_key)) if selected_key else {}
    plan_id = str(selected.get("plan_id") or "")
    span_refs = tuple(str(ref) for ref in selected.get("span_refs") or [] if ref)
    relation = str(selected.get("polarity_relation") or "")
    if (
        not plan_id
        or not span_refs
        or relation
        not in {
            "proposition_support",
            "explicit_contradiction",
        }
    ):
        return {}
    return {
        plan_id: {
            "plan_id": plan_id,
            "polarity_relation": relation,
            "span_refs": span_refs,
            "slot_refs": deepcopy(selected.get("slot_refs") or {}),
            "event_binding_id": str(selected.get("event_binding_id") or ""),
            "required_object_tokens": list(
                selected.get("required_object_tokens") or []
            ),
            "covered_object_tokens": list(selected.get("covered_object_tokens") or []),
            "event_subplans": deepcopy(selected.get("event_subplans") or []),
            "comparison_relation": deepcopy(selected.get("comparison_relation")),
        }
    }


def _payload(reasons: list[str], **values: Any) -> dict[str, Any]:
    unique = list(dict.fromkeys(reason for reason in reasons if reason))
    return {
        "status": "complete" if not unique else "incomplete",
        "incompleteness_reasons": unique,
        **values,
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _mapping_list(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, Mapping)]
