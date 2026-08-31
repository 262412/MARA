from __future__ import annotations

import json
from collections.abc import Mapping
from copy import deepcopy
from types import SimpleNamespace
from typing import Any

from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.frozen_canonical_proposition_projection import (
    frozen_canonical_plan_projection_from_bundle,
    frozen_slot_support_by_ref,
)
from ktem.docqa.fusion_stage import FUSION_STAGE_CONTRACT, fusion_stage_snapshot
from ktem.docqa.question_proposition import (
    applicable_proposition_evidence_slots,
    build_question_proposition,
)
from ktem.docqa.semantic_evidence_set_authority import (
    semantic_evidence_set_claim_authority,
)
from ktem.reasoning.mara_qasper_semantic_pack import (
    qasper_canonical_evidence_plans,
    qasper_source_packing_observation,
)
from ktem.reasoning.mara_semantic_candidate_policy import candidate_bound_response

BOUND_STATES = frozenset({"relation_bound_support", "relation_bound_contradiction"})
PRODUCTION_CONTRACT = "qasper_natural_production_authority_probe.v2"


def candidate_label(
    candidate_generation: Mapping[str, Any],
    metadata: Mapping[str, Any],
    row: Mapping[str, Any],
) -> str:
    sources = (
        candidate_generation,
        _mapping(metadata.get("qasper_candidate_generation")),
        _mapping(row.get("engine_terminal_state")),
    )
    for source in sources:
        for key in (
            "verifier_input_candidate",
            "typed_candidate",
            "raw_candidate",
            "candidate",
            "raw_candidate_label",
        ):
            value = str(source.get(key) or "").strip()
            if value:
                return value
    return ""


def source_stage_response(metadata: Mapping[str, Any], stage: str) -> str:
    verifier = _mapping(metadata.get("semantic_proposition_verifier"))
    events = _mapping(verifier.get("debug_trace")).get("events")
    if not isinstance(events, list):
        return ""
    for event in reversed(events):
        attempts = _mapping(_mapping(event.get("transaction")).get(stage)).get(
            "attempts"
        )
        if not isinstance(attempts, list):
            continue
        for attempt in reversed(attempts):
            raw = str(_mapping(attempt).get("raw_response") or "")
            if raw:
                return raw
    return ""


def proposal_plan_id(raw_proposal: str) -> str:
    try:
        payload = json.loads(raw_proposal)
    except (TypeError, json.JSONDecodeError):
        return ""
    return (
        str(payload.get("canonical_evidence_plan_id") or "")
        if isinstance(payload, dict)
        else ""
    )


def frozen_plan_projection(
    bundle: EvidenceBundle,
    context: Any,
    *,
    question: str,
    plan_id: str,
) -> tuple[Any | None, str]:
    if not plan_id:
        return None, "canonical_plan_projection_plan_missing"
    proposition = build_question_proposition(question)
    plan = _mapping((qasper_canonical_evidence_plans(bundle) or {}).get(plan_id))
    refs = tuple(str(ref) for ref in plan.get("span_refs") or [] if str(ref))
    slot_support, support_reason = frozen_slot_support_by_ref(refs, context.slots)
    if support_reason:
        return None, support_reason
    return frozen_canonical_plan_projection_from_bundle(
        bundle,
        plan_id=plan_id,
        proposition=proposition,
        expected_slots=applicable_proposition_evidence_slots(proposition),
        slot_support_by_ref=slot_support,
    )


def audit_replay_response(
    raw_audit: str,
    projection: Any | None,
) -> tuple[str, str]:
    if raw_audit:
        return raw_audit, "recorded"
    if projection is None:
        return "", "missing"
    checks = {
        premise_ref: {
            "fragment_entailed": True,
            "scope_consistent": True,
            "evidence_relation_valid": True,
            "proposition_slot_checks": {
                slot: {
                    "binding_valid": True,
                    "evidence_ref": str(
                        value.get("evidence_ref") or f"{premise_ref}:{slot}"
                    ),
                }
                for slot, value in _mapping(slot_evidence).items()
            },
        }
        for premise_ref, slot_evidence in projection.audit_slot_evidence.items()
    }
    payload = {
        "premise_checks": checks,
        "jointly_entails": True,
        "each_premise_required": True,
        "contradiction_free": True,
        "conclusion_check": {
            "conclusion_entailed": True,
            "actor_consistent": True,
            "predicate_consistent": True,
            "object_consistent": True,
            "polarity_consistent": True,
            "quantifier_consistent": True,
            "scope_consistent": True,
        },
    }
    return json.dumps(payload, sort_keys=True), "controlled_from_frozen_plan"


def source_semantic_trace_observation(
    metadata: Mapping[str, Any],
) -> dict[str, Any]:
    trace = _mapping(metadata.get("semantic_proposition_verifier"))
    return {
        "status": "recorded",
        "source_status": str(trace.get("status") or ""),
        "reason": str(trace.get("reason") or ""),
        "raw_proposal_present": bool(source_stage_response(metadata, "proposal")),
        "raw_audit_present": bool(source_stage_response(metadata, "audit")),
    }


def record_production_verifier_trace(
    metadata: dict[str, Any],
    *,
    context: Any,
    outcome: Any,
    response: Mapping[str, Any] | None,
) -> None:
    pack = _mapping(metadata.get("qasper_canonical_semantic_pack"))
    diagnostics = _mapping(outcome.diagnostics)
    metadata["semantic_proposition_verifier"] = {
        "contract_id": "semantic_proposition_verifier_runtime.v3",
        "status": str(outcome.status or ""),
        "reason": str(outcome.reason or ""),
        "model": "natural-probe-proposal-v1",
        "release_mode": True,
        "semantic_pack_digest": str(pack.get("semantic_pack_digest") or ""),
        "canonical_span_universe_digest": str(pack.get("span_universe_digest") or ""),
        "candidate_transaction_id": str(pack.get("candidate_transaction_id") or ""),
        "canonical_pack_continuity_status": (
            "preserved" if response is not None else "not_bound"
        ),
        "candidate_verification_status": str(
            (response or {}).get("candidate_verification_status") or ""
        ),
        "audit_status": str(diagnostics.get("audit_status") or ""),
        "audit_reason": str(diagnostics.get("audit_reason") or ""),
        "proposal_model_call_count": int(outcome.proposal_call_count or 0),
        "audit_model_call_count": int(outcome.audit_call_count or 0),
        "transaction_id": str(context.transaction_id or ""),
    }


def finish_production_path(
    metadata: dict[str, Any],
    *,
    context: Any,
    bundle: EvidenceBundle,
    outcome: Any,
    candidate: str,
    source_metadata: Mapping[str, Any],
    question: str,
    source_trace: dict[str, Any],
    projection: dict[str, Any],
    audit_response_source: str,
) -> dict[str, Any]:
    response = (
        candidate_bound_response(outcome.value, candidate)
        if outcome.value is not None
        else None
    )
    record_production_verifier_trace(
        metadata, context=context, outcome=outcome, response=response
    )
    authority = semantic_evidence_set_claim_authority(
        production_request(source_metadata, context, question),
        question,
        candidate,
        EvidenceBundle(
            route=bundle.route,
            items=deepcopy(bundle.items),
            metadata=metadata,
        ),
        lambda *_args: deepcopy(response) if response is not None else None,
    )
    return production_path_result(
        candidate,
        source_trace=source_trace,
        projection=projection,
        outcome=outcome,
        authority=authority,
        response=response,
        audit_response_source=audit_response_source,
    )


def production_request(
    metadata: Mapping[str, Any],
    context: Any,
    question: str,
) -> Any:
    source_observation = _mapping(qasper_source_packing_observation(context.bundle))
    source_snapshot = _mapping(source_observation.get("source_input_snapshot"))
    return SimpleNamespace(
        origin="benchmark",
        verification_domain="qasper",
        dataset_family="qasper",
        task_type="boolean",
        answer_type="boolean",
        verification_mode="strict",
        question=question,
        query=question,
        query_plan=deepcopy(source_snapshot.get("query_plan")),
        trace_context={
            "trace_group_id": str(
                context.candidate_generation.get("trace_group_id") or ""
            ),
            "benchmark_route_id": str(
                context.candidate_generation.get("benchmark_route_id") or ""
            ),
        },
    )


def production_path_result(
    candidate: str,
    *,
    source_trace: dict[str, Any],
    projection: dict[str, Any],
    outcome: Any,
    authority: Any,
    response: Mapping[str, Any] | None,
    audit_response_source: str,
) -> dict[str, Any]:
    diagnostics = _mapping(outcome.diagnostics)
    preflight_called = projection.get("status") == "passed"
    preflight_reason = str(diagnostics.get("audit_reason") or "")
    if not preflight_reason and str(outcome.reason or "").startswith("pre_audit"):
        preflight_reason = str(outcome.reason)
    return {
        "contract_id": PRODUCTION_CONTRACT,
        "source_trace": source_trace,
        "frozen_plan_projection": projection,
        "semantic_transaction": {
            "called": True,
            "status": str(outcome.status or ""),
            "reason": str(outcome.reason or ""),
            "proposal_call_count": int(outcome.proposal_call_count or 0),
            "audit_call_count": int(outcome.audit_call_count or 0),
            "canonical_plan_projection_status": str(
                diagnostics.get("canonical_plan_projection_status") or ""
            ),
            "audit_status": str(diagnostics.get("audit_status") or ""),
            "audit_reason": str(diagnostics.get("audit_reason") or ""),
        },
        "audit_preflight": {
            "called": preflight_called,
            "status": "passed"
            if preflight_called and not preflight_reason
            else "failed",
            "reason": preflight_reason,
            "audit_response_source": audit_response_source,
            "implementation": "run_semantic_proposition_transaction.audit_stage",
        },
        "audit_response_source": audit_response_source,
        "boolean_authority": authority_observation(
            authority,
            candidate=candidate,
            items=response.get("premises") if isinstance(response, Mapping) else [],
        ),
    }


def authority_observation(
    authority: Any,
    *,
    candidate: str,
    items: Any,
) -> dict[str, Any]:
    supporting = tuple(getattr(authority, "supporting", ()) or ()) if authority else ()
    contradicting = (
        tuple(getattr(authority, "contradicting", ()) or ()) if authority else ()
    )
    supporting_ids = [str(value.evidence_id or "") for value in supporting]
    contradicting_ids = [str(value.evidence_id or "") for value in contradicting]
    evidence_ids = {
        str(item.get("evidence_id") or "")
        for item in items
        if isinstance(item, Mapping)
    }
    derivations = (
        tuple(getattr(authority, "authority_derivations", ()) or ())
        if authority
        else ()
    )
    return {
        "called": True,
        "candidate": candidate,
        "status": str(getattr(authority, "status", "") or "") if authority else "",
        "reason": str(getattr(authority, "reason", "") or "")
        if authority
        else "semantic_authority_not_bound",
        "input_answer_polarity": str(
            getattr(authority, "input_answer_polarity", "") or ""
        )
        if authority
        else candidate,
        "canonical_answer_polarity": str(
            getattr(authority, "canonical_answer_polarity", "") or ""
        )
        if authority
        else "",
        "supporting_evidence_ids": supporting_ids,
        "contradicting_evidence_ids": contradicting_ids,
        "authority_derivation_count": len(derivations),
        "selected_derivation_id": str(
            getattr(authority, "selected_derivation_id", "") or ""
        )
        if authority
        else "",
        "evidence_ids_are_bound": bool(authority)
        and set(supporting_ids + contradicting_ids) <= evidence_ids,
        "derivation_status": "bound" if derivations else "not_bound",
    }


def not_applicable_production_path(
    candidate: str,
    *,
    source_trace: dict[str, Any],
) -> dict[str, Any]:
    not_applicable = {
        "called": False,
        "status": "not_applicable",
        "reason": "semantic_binding_not_answerable",
    }
    return {
        "contract_id": PRODUCTION_CONTRACT,
        "source_trace": source_trace,
        "frozen_plan_projection": dict(not_applicable),
        "semantic_transaction": dict(not_applicable),
        "audit_preflight": dict(not_applicable),
        "audit_response_source": "not_applicable",
        "boolean_authority": {
            **not_applicable,
            "candidate": candidate,
            "supporting_evidence_ids": [],
            "contradicting_evidence_ids": [],
            "authority_derivation_count": 0,
            "selected_derivation_id": "",
            "evidence_ids_are_bound": False,
            "derivation_status": "not_applicable",
        },
    }


def production_failure_path(
    candidate: str,
    *,
    source_trace: dict[str, Any],
    projection: dict[str, Any],
    audit_response_source: str,
    reason: str,
) -> dict[str, Any]:
    failure = {"called": True, "status": "failed", "reason": reason}
    return {
        "contract_id": PRODUCTION_CONTRACT,
        "source_trace": source_trace,
        "frozen_plan_projection": projection,
        "semantic_transaction": dict(failure),
        "audit_preflight": {
            "called": projection.get("status") == "passed",
            "status": "failed",
            "reason": reason,
            "audit_response_source": audit_response_source,
        },
        "audit_response_source": audit_response_source,
        "boolean_authority": {
            **failure,
            "candidate": candidate,
            "supporting_evidence_ids": [],
            "contradicting_evidence_ids": [],
            "authority_derivation_count": 0,
            "selected_derivation_id": "",
            "evidence_ids_are_bound": False,
            "derivation_status": "not_bound",
        },
    }


def fusion_replay_prediction(
    row: Mapping[str, Any],
    bundle: EvidenceBundle,
) -> dict[str, Any]:
    """Materialize a current producer snapshot for the frozen route bundle."""

    metadata = deepcopy(bundle.metadata)
    items = deepcopy(bundle.items)
    snapshot = fusion_stage_snapshot(bundle.route, items, items, fusion_trace=None)
    metadata.update(
        {
            "canonical_candidate_evidence": deepcopy(items),
            "candidate_ranked_evidence": deepcopy(items),
            "fused_evidence": deepcopy(items),
            "fusion_stage_snapshot": deepcopy(snapshot),
        }
    )
    ranking = _mapping(metadata.get("ranking_trace"))
    ranking.update(
        {
            "fusion_stage_contract_id": FUSION_STAGE_CONTRACT,
            "candidate_stage": snapshot["candidate_stage"],
            "fusion_stage_snapshot": deepcopy(snapshot),
        }
    )
    metadata["ranking_trace"] = ranking
    return {
        "example_id": str(row.get("example_id") or ""),
        "route": str(row.get("route") or ""),
        "evidence_bundle": {
            "route": bundle.route,
            "items": items,
            "metadata": metadata,
        },
        "evidence_metadata": metadata,
    }


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}
