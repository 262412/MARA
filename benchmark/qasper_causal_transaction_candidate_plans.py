from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest, is_sha256


def candidate_plans_stage_payload(
    construction: Mapping[str, Any],
    generator_construction: Mapping[str, Any],
) -> dict[str, Any]:
    decisions = deepcopy(construction.get("candidate_decisions") or [])
    selector_decisions = deepcopy(construction.get("selector_pool_decisions") or [])
    enumeration_policy = deepcopy(construction.get("enumeration_policy") or {})
    valid_counts = deepcopy(_mapping(construction.get("valid_candidate_counts")))
    reasons = _candidate_plan_integrity_reasons(
        construction,
        generator_construction,
        decisions=decisions,
        selector_decisions=selector_decisions,
        enumeration_policy=enumeration_policy,
    )
    return _payload(
        reasons,
        plan_construction_source="frozen_canonical_semantic_pack",
        plan_construction_contract_id=str(construction.get("contract_id") or ""),
        plan_construction_digest=canonical_digest(construction),
        candidate_generator_plan_construction_digest=canonical_digest(
            generator_construction
        ),
        enumeration_policy=enumeration_policy,
        enumeration_policy_digest=str(
            construction.get("enumeration_policy_digest") or ""
        ),
        selector_pool_decisions=selector_decisions,
        selector_pool_decisions_digest=str(
            construction.get("selector_pool_decisions_digest") or ""
        ),
        candidate_plan_count=int(construction.get("candidate_count") or 0),
        relation_analysis_count=int(construction.get("relation_analysis_count") or 0),
        candidate_decision_count=int(construction.get("candidate_decision_count") or 0),
        valid_candidate_counts=valid_counts,
        legal_plan_count=sum(int(value or 0) for value in valid_counts.values()),
        candidate_plans=decisions,
        candidate_plans_digest=str(
            construction.get("candidate_decisions_digest") or ""
        ),
        selected_candidate_ids=deepcopy(
            construction.get("selected_candidate_ids") or {}
        ),
        best_rejected_candidates=deepcopy(
            construction.get("best_rejected")
            or construction.get("best_rejected_candidates")
            or {}
        ),
    )


def _candidate_plan_integrity_reasons(
    construction: Mapping[str, Any],
    generator_construction: Mapping[str, Any],
    *,
    decisions: list[Any],
    selector_decisions: list[Any],
    enumeration_policy: Mapping[str, Any],
) -> list[str]:
    reasons = []
    if construction.get("contract_id") != "canonical_plan_construction_trace.v1":
        reasons.append("frozen_candidate_plan_trace_missing")
    if construction.get("enumeration_policy_complete") is not True:
        reasons.append("candidate_plan_enumeration_policy_incomplete")
    _append_digest_reason(
        reasons,
        enumeration_policy,
        construction.get("enumeration_policy_digest"),
        label="candidate_plan_enumeration_policy",
    )
    if construction.get("selector_pool_decisions_complete") is not True:
        reasons.append("selector_pool_decisions_incomplete")
    if int(construction.get("selector_pool_decision_count") or 0) != len(
        selector_decisions
    ):
        reasons.append("selector_pool_decision_count_mismatch")
    _append_digest_reason(
        reasons,
        selector_decisions,
        construction.get("selector_pool_decisions_digest"),
        label="selector_pool_decisions",
    )
    if construction.get("candidate_decisions_complete") is not True:
        reasons.append("candidate_plan_enumeration_incomplete")
    decision_count = int(construction.get("candidate_decision_count") or 0)
    analysis_count = int(construction.get("relation_analysis_count") or 0)
    if analysis_count <= 0:
        reasons.append("candidate_plan_relation_analysis_missing")
    if decision_count != analysis_count or decision_count != len(decisions):
        reasons.append("candidate_plan_count_mismatch")
    _append_digest_reason(
        reasons,
        decisions,
        construction.get("candidate_decisions_digest"),
        label="candidate_plans",
    )
    if not _candidate_plan_decisions_typed(decisions):
        reasons.append("candidate_plan_decision_invalid")
    if any(
        _mapping(decision).get("decision") == "rejected"
        and not _mapping(decision).get("rejection_reasons")
        for decision in decisions
    ):
        reasons.append("rejected_plan_typed_reason_missing")
    if not generator_construction:
        reasons.append("candidate_generator_plan_construction_missing")
    elif canonical_digest(generator_construction) != canonical_digest(construction):
        reasons.append("candidate_generator_plan_construction_mismatch")
    return reasons


def _append_digest_reason(
    reasons: list[str],
    value: Any,
    recorded: Any,
    *,
    label: str,
) -> None:
    if not is_sha256(recorded):
        reasons.append(f"{label}_digest_missing")
    elif canonical_digest(value) != recorded:
        reasons.append(f"{label}_digest_mismatch")


def _candidate_plan_decisions_typed(decisions: list[Any]) -> bool:
    return bool(decisions) and all(
        _mapping(decision).get("candidate_id")
        and _mapping(decision).get("relation")
        and _mapping(decision).get("origin")
        and _mapping(decision).get("decision") in {"accepted", "rejected"}
        for decision in decisions
    )


def _payload(reasons: list[str], **values: Any) -> dict[str, Any]:
    unique = list(dict.fromkeys(reason for reason in reasons if reason))
    return {
        "status": "complete" if not unique else "incomplete",
        "incompleteness_reasons": unique,
        **values,
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
