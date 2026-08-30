from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from .mara_qasper_candidate_identity import candidate_digest


def plan_decision_trace_fields(trace: Mapping[str, Any]) -> dict[str, Any]:
    """Copy exhaustive selector/candidate decisions into persisted lineage."""

    return {
        "enumeration_policy_complete": trace.get("enumeration_policy_complete") is True,
        "enumeration_policy_digest": str(trace.get("enumeration_policy_digest") or ""),
        "enumeration_policy": deepcopy(trace.get("enumeration_policy") or {}),
        "selector_pool_decisions_complete": trace.get(
            "selector_pool_decisions_complete"
        )
        is True,
        "selector_pool_decision_count": int(
            trace.get("selector_pool_decision_count") or 0
        ),
        "selector_pool_decisions_digest": str(
            trace.get("selector_pool_decisions_digest") or ""
        ),
        "selector_pool_decisions": deepcopy(trace.get("selector_pool_decisions") or []),
        "relation_analysis_count": int(trace.get("relation_analysis_count") or 0),
        "candidate_decisions_complete": trace.get("candidate_decisions_complete")
        is True,
        "candidate_decision_count": int(trace.get("candidate_decision_count") or 0),
        "candidate_decisions_digest": str(
            trace.get("candidate_decisions_digest") or ""
        ),
        "candidate_decisions": deepcopy(trace.get("candidate_decisions") or []),
        "selected_candidate_ids": deepcopy(trace.get("selected_candidate_ids") or {}),
        "planner_binding_state": str(trace.get("binding_state") or ""),
        "planner_ambiguous": trace.get("ambiguous") is True
        or str(trace.get("binding_state") or "") in {"ambiguous", "ambiguous_conflict"},
    }


def record_plan_decisive_transition(
    lineage: dict[str, Any],
    *,
    candidate: str,
) -> None:
    construction = lineage.get("plan_construction")
    if not isinstance(construction, Mapping):
        return
    legal_plan_count = int(construction.get("legal_plan_count") or 0)
    normalized_candidate = str(candidate or "").casefold()
    if legal_plan_count > 0 and normalized_candidate != "unanswerable":
        return
    decisions = construction.get("candidate_decisions")
    decisions = decisions if isinstance(decisions, list) else []
    rejection_reason_counts: dict[str, int] = {}
    for decision in decisions:
        if not isinstance(decision, Mapping):
            continue
        for reason in decision.get("rejection_reasons") or []:
            key = str(reason or "")
            if key:
                rejection_reason_counts[key] = rejection_reason_counts.get(key, 0) + 1
    context = {
        "candidate": str(candidate or ""),
        "semantic_plan_status": str(construction.get("semantic_plan_status") or ""),
        "plan_reason": str(construction.get("reason") or ""),
        "planner_binding_state": str(construction.get("planner_binding_state") or ""),
        "planner_ambiguous": construction.get("planner_ambiguous") is True,
        "candidate_decision_count": int(
            construction.get("candidate_decision_count") or 0
        ),
        "candidate_decisions_digest": str(
            construction.get("candidate_decisions_digest") or ""
        ),
        "rejection_reason_counts": rejection_reason_counts,
    }
    if legal_plan_count > 0:
        context.update(
            legal_plan_count=legal_plan_count,
            selected_candidate_ids=deepcopy(
                construction.get("selected_candidate_ids") or {}
            ),
        )
        lineage["first_decisive_transition"] = {
            "stage": "candidate_generation",
            "decision": "unanswerable_despite_legal_local_plan",
            "candidate": normalized_candidate,
            "classification_hint": "candidate_plan_conflict",
            "decision_context": context,
            "decision_context_digest": candidate_digest(context),
            "observation_digest": candidate_digest(
                {
                    "candidate": normalized_candidate,
                    "legal_plan_count": legal_plan_count,
                    "candidate_decisions_digest": context["candidate_decisions_digest"],
                }
            ),
        }
        return
    lineage["first_decisive_transition"] = {
        "stage": "plan_construction",
        "decision": "no_legal_evidence_plan",
        "candidate": str(candidate or ""),
        "classification_hint": (
            "ambiguous_plan_set"
            if context["planner_ambiguous"]
            else "candidate_not_answerable"
            if context["semantic_plan_status"] == "not_applicable"
            else "unexpected_no_legal_plan"
        ),
        "decision_context": context,
        "decision_context_digest": candidate_digest(context),
        "observation_digest": candidate_digest(construction),
    }


def record_candidate_bound_decisive_transition(
    lineage: dict[str, Any],
    *,
    status: str,
    reason: str,
    audit_reason: str,
) -> None:
    """Record an audited unknown as the terminal decision boundary."""

    existing = _mapping(lineage.get("first_decisive_transition"))
    if existing.get("stage") in {"plan_construction", "candidate_generation"}:
        return
    construction = _mapping(lineage.get("plan_construction"))
    context = {
        "candidate": str(lineage.get("candidate") or ""),
        "status": status,
        "reason": reason,
        "audit_status": "candidate_bound",
        "audit_reason": audit_reason,
        "legal_plan_count": int(construction.get("legal_plan_count") or 0),
        "selected_plan_id": str(construction.get("selected_plan_id") or ""),
    }
    lineage["first_decisive_transition"] = {
        "stage": "auditor_semantics",
        "decision": "candidate_bound",
        "candidate": context["candidate"],
        "classification_hint": "candidate_bound_terminal_abstention",
        "decision_context": context,
        "decision_context_digest": candidate_digest(context),
        "observation_digest": candidate_digest(
            {
                "audit_status": context["audit_status"],
                "audit_reason": context["audit_reason"],
                "selected_plan_id": context["selected_plan_id"],
            }
        ),
    }


def finalize_decisive_transition(
    lineage: dict[str, Any],
    *,
    status: str,
    reason: str,
) -> None:
    if lineage.get("first_decisive_transition"):
        return
    inconsistency = lineage.get("first_inconsistency")
    if isinstance(inconsistency, Mapping) and inconsistency:
        context = {
            "first_inconsistency": dict(inconsistency),
            "local_projection": deepcopy(lineage.get("local_projection") or {}),
            "plan_selected_id": str(
                _mapping(lineage.get("plan_construction")).get("selected_plan_id") or ""
            ),
            "audit": deepcopy(lineage.get("audit") or {}),
        }
        lineage["first_decisive_transition"] = {
            "stage": str(inconsistency.get("stage") or "transaction_runtime"),
            "decision": str(inconsistency.get("reason") or reason or status),
            "candidate": "",
            "classification_hint": "runtime_inconsistency",
            "decision_context": context,
            "decision_context_digest": candidate_digest(context),
            "observation_digest": str(
                inconsistency.get("raw_response_digest")
                or candidate_digest(inconsistency)
            ),
        }
        return
    context = {"status": status, "reason": reason}
    lineage["first_decisive_transition"] = {
        "stage": "terminal_semantic_commit",
        "decision": "accepted" if status == "parsed" else str(reason or status),
        "candidate": "",
        "classification_hint": "terminal_commit",
        "decision_context": context,
        "decision_context_digest": candidate_digest(context),
        "observation_digest": candidate_digest(context),
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
