from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest

_PLAN_RELATIONS = {
    "proposition_support": "support_plan",
    "explicit_contradiction": "contradiction_plan",
}


def selected_plan_stage_payload(
    frozen_binding: Mapping[str, Any],
    generator_binding: Mapping[str, Any],
    proposal_value: Mapping[str, Any],
) -> dict[str, Any]:
    canonical_plan = _mapping(frozen_binding.get("canonical_evidence_plan"))
    construction = _mapping(frozen_binding.get("plan_construction_trace"))
    selected_candidate_ids = deepcopy(
        _mapping(construction.get("selected_candidate_ids"))
    )
    allowed_local_plans = _allowed_local_plans(canonical_plan)
    allowed_local_plan_ids = list(allowed_local_plans.values())
    selected = str(proposal_value.get("canonical_evidence_plan_id") or "")
    reasons = _selection_integrity_reasons(
        frozen_binding,
        generator_binding,
        canonical_plan=canonical_plan,
        selected_candidate_ids=selected_candidate_ids,
        allowed_local_plans=allowed_local_plans,
        selected=selected,
    )
    return _payload(
        reasons,
        selection_authority_source="frozen_canonical_semantic_pack",
        selection_status="selected" if selected else "not_selected",
        selection_reason=_selection_reason(selected, allowed_local_plan_ids),
        selected_plan_id=selected,
        allowed_local_plans=allowed_local_plans,
        allowed_local_plan_ids=allowed_local_plan_ids,
        allowed_local_plan_ids_digest=canonical_digest(allowed_local_plan_ids),
        legal_plan_count=len(allowed_local_plan_ids),
        selected_candidate_ids=selected_candidate_ids,
        canonical_evidence_plan=deepcopy(canonical_plan),
        frozen_selection_binding_digest=canonical_digest(frozen_binding),
        candidate_generator_selection_binding_digest=canonical_digest(
            generator_binding
        ),
    )


def _selection_integrity_reasons(
    frozen_binding: Mapping[str, Any],
    generator_binding: Mapping[str, Any],
    *,
    canonical_plan: Mapping[str, Any],
    selected_candidate_ids: Mapping[str, Any],
    allowed_local_plans: Mapping[str, str],
    selected: str,
) -> list[str]:
    reasons = []
    if not frozen_binding:
        reasons.append("frozen_selection_binding_missing")
    if canonical_plan.get("contract_id") != "canonical_proposition_evidence_plan.v2":
        reasons.append("canonical_evidence_plan_missing")
    if not _mapping(frozen_binding.get("plan_construction_trace")):
        reasons.append("frozen_plan_construction_missing")
    if any(relation not in selected_candidate_ids for relation in _PLAN_RELATIONS):
        reasons.append("selected_candidate_ids_incomplete")
    if any(
        bool(allowed_local_plans.get(relation))
        != bool(selected_candidate_ids.get(relation))
        for relation in _PLAN_RELATIONS
    ):
        reasons.append("selected_candidate_plan_mapping_mismatch")
    if not generator_binding:
        reasons.append("candidate_generator_selection_binding_missing")
    elif canonical_digest(generator_binding) != canonical_digest(frozen_binding):
        reasons.append("candidate_generator_selection_binding_mismatch")
    if selected and selected not in allowed_local_plans.values():
        reasons.append("selected_plan_id_not_in_frozen_local_plans")
    return reasons


def _allowed_local_plans(canonical_plan: Mapping[str, Any]) -> dict[str, str]:
    output = {}
    for relation, field in _PLAN_RELATIONS.items():
        plan_id = str(_mapping(canonical_plan.get(field)).get("plan_id") or "")
        if plan_id:
            output[relation] = plan_id
    return output


def _selection_reason(selected: str, allowed_local_plan_ids: list[str]) -> str:
    if selected:
        return "model_selected_frozen_local_plan"
    if allowed_local_plan_ids:
        return "model_did_not_select_plan"
    return "no_legal_plan"


def _payload(reasons: list[str], **values: Any) -> dict[str, Any]:
    unique = list(dict.fromkeys(reason for reason in reasons if reason))
    return {
        "status": "complete" if not unique else "incomplete",
        "incompleteness_reasons": unique,
        **values,
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
