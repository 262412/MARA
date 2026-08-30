from __future__ import annotations

import hashlib
import json
from typing import Any

from benchmark.tests.contract_smoke_fixtures import _fixture_digest
from benchmark.tests.qasper_debug_lineage_source_helpers import (
    debug_source_packing as _debug_source_packing,
)


def _debug_verifier_state_fields(
    relation: str,
    audit_status: str,
) -> dict[str, Any]:
    safe_terminal = relation != "supported"
    support_slots = ["support:boolean_proposition"] if relation == "supported" else []
    return {
        "audit_contract_id": (
            "candidate_verifier_audit.v2"
            if relation == "unknown"
            else "semantic_entailment_audit.v3"
        ),
        "audit_status": (
            "verified"
            if audit_status == "passed" and not safe_terminal
            else "candidate_bound"
            if audit_status == "passed"
            else "failed"
        ),
        "required_slot_ids": support_slots,
        "verified_support_slot_ids": support_slots,
    }


def _debug_semantic_chain_fixture(
    transaction_id: str,
    candidate: str,
    relation: str,
    audit_status: str,
    typed_conclusion: dict[str, Any],
    conclusion_audit: dict[str, Any],
    pack_identity: dict[str, str],
    canonical_plan_id: str,
) -> dict[str, Any]:
    selected_plan_id = "" if relation == "unknown" else canonical_plan_id
    return {
        "debug_trace": _debug_semantic_trace(
            candidate,
            relation,
            audit_status,
            typed_conclusion,
            conclusion_audit,
            plan_id=selected_plan_id,
        ),
        "semantic_data_lineage": _debug_semantic_data_lineage(
            candidate,
            relation,
            audit_status,
            pack_identity,
            allowed_plan_id=canonical_plan_id,
            selected_plan_id=selected_plan_id,
        ),
    }


def _debug_semantic_trace(
    candidate: str,
    relation: str,
    audit_status: str,
    typed_conclusion: dict[str, Any],
    conclusion_audit: dict[str, Any],
    *,
    plan_id: str,
) -> dict[str, Any]:
    proposal_raw = _debug_plan_selection_raw(relation, plan_id)
    audit_raw = '{"status":"verified"}'
    return {
        "contract_id": "semantic_proposition_debug_trace.v3",
        "event_count": 1,
        "dropped_event_count": 0,
        "events": [
            {
                "event": "model_transaction",
                "transaction": {
                    "proposal": {
                        "status": "parsed",
                        "attempts": [
                            {
                                "attempt": 1,
                                "attempt_id": "proposal-attempt",
                                "raw_response": proposal_raw,
                                "finish_reason": "stop",
                                "parse_failure_reason": "",
                                "provider_failure_reason": "",
                                "parsed_value": {
                                    "contract_id": "semantic_proposition_verdict.v4",
                                    "verdict": candidate,
                                    "candidate_judgment": relation,
                                    "canonical_evidence_plan_id": plan_id,
                                },
                            }
                        ],
                    },
                    "audit": {
                        "status": "parsed",
                        "attempts": [
                            {
                                "attempt": 1,
                                "attempt_id": "audit-attempt",
                                "raw_response": audit_raw,
                                "finish_reason": "stop",
                                "parse_failure_reason": "",
                                "provider_failure_reason": "",
                                "parsed_value": {"status": audit_status},
                            }
                        ],
                    },
                },
                "outcome": {
                    "status": "parsed",
                    "reason": "fixture_audit",
                    "verdict": candidate,
                    "audit_status": "verified"
                    if audit_status == "passed" and relation == "supported"
                    else "candidate_bound"
                    if audit_status == "passed"
                    else "failed",
                    "audit_reason": "fixture_audit",
                    "typed_conclusion": typed_conclusion,
                    "conclusion_audit": conclusion_audit,
                },
            }
        ],
    }


def _debug_semantic_data_lineage(
    candidate: str,
    relation: str,
    audit_status: str,
    pack_identity: dict[str, str],
    *,
    allowed_plan_id: str,
    selected_plan_id: str,
) -> dict[str, Any]:
    proposal_raw = _debug_plan_selection_raw(relation, selected_plan_id)
    audit_raw = '{"status":"verified"}'
    failed = audit_status == "failed"
    return {
        "contract_id": "semantic_proposition_data_lineage.v1",
        "status": "failed" if failed else "passed",
        "identities": {
            "semantic_pack_digest": pack_identity["semantic_pack_digest"],
            "canonical_span_universe_digest": pack_identity["span_universe_digest"],
            "candidate_transaction_id": pack_identity["candidate_transaction_id"],
        },
        "proposal_contract": {
            "mode": "canonical_plan_selection",
            "allowed_plan_ids": [allowed_plan_id] if allowed_plan_id else [],
            "response_schema_digest": _fixture_digest(
                {
                    "schema": "canonical_plan_selection",
                    "plan_id": allowed_plan_id,
                }
            ),
        },
        "proposal_attempts": [
            {
                "attempt": 1,
                "raw_response_digest": _raw_response_digest(proposal_raw),
                "parse_failure_reason": "",
                "provider_failure_reason": "",
            }
        ],
        "local_projection": {
            "status": "passed",
            "selected_plan_id": selected_plan_id,
        },
        **_debug_lineage_plan_fields(
            pack_identity,
            allowed_plan_id=allowed_plan_id,
            selected_plan_id=selected_plan_id,
        ),
        "audit": {
            "status": "parsed",
            "reason": "",
            "attempts": [
                {
                    "attempt": 1,
                    "raw_response_digest": _raw_response_digest(audit_raw),
                    "parse_failure_reason": "",
                    "provider_failure_reason": "",
                }
            ],
        },
        "first_inconsistency": (
            {
                "stage": "auditor_semantics",
                "reason": "fixture_audit",
                "attempt": 1,
                "raw_response_digest": _raw_response_digest(audit_raw),
            }
            if failed
            else {}
        ),
        "first_decisive_transition": _debug_first_decisive_transition(
            audit_status=(
                "candidate_bound"
                if relation == "unknown" and audit_status == "passed"
                else audit_status
            ),
            legal_plan_count=int(bool(allowed_plan_id)),
            candidate=candidate,
        ),
    }


def _debug_lineage_plan_fields(
    pack_identity: dict[str, str],
    *,
    allowed_plan_id: str,
    selected_plan_id: str,
) -> dict[str, Any]:
    selector_ref = "E1:S1"
    event_id = "fixture-event"
    return {
        "source_packing": _debug_source_packing(pack_identity),
        "selector": {
            "status": "passed",
            "universe": [selector_ref],
            "universe_refs": [selector_ref],
            "universe_records": [
                {
                    "evidence_id": "span:paper:s1",
                    "selector_id": selector_ref,
                    "event_id": event_id,
                }
            ],
            "candidate_count": 1,
            "event_ids": [event_id],
        },
        "plan_construction": _debug_plan_construction(
            allowed_plan_id,
            selected_plan_id=selected_plan_id,
            selector_ref=selector_ref,
            event_id=event_id,
        ),
    }


def _debug_plan_construction(
    allowed_plan_id: str,
    *,
    selected_plan_id: str,
    selector_ref: str,
    event_id: str,
) -> dict[str, Any]:
    covered = ["actor", "predicate", "object"] if selected_plan_id else []
    decisions = [
        {
            "candidate_id": _fixture_digest(
                {"relation": relation, "selector_ref": selector_ref}
            ),
            "relation": relation,
            "span_refs": [selector_ref],
            "decision": (
                "accepted"
                if allowed_plan_id and relation == "proposition_support"
                else "rejected"
            ),
            "origin": "event_local",
            "rejection_reasons": (
                []
                if allowed_plan_id and relation == "proposition_support"
                else ["fixture_rejection"]
            ),
        }
        for relation in ("proposition_support", "explicit_contradiction")
    ]
    return {
        "status": "passed",
        "transport_status": "passed",
        "semantic_plan_status": "passed" if allowed_plan_id else "not_applicable",
        "universe": [selector_ref],
        "universe_refs": [selector_ref],
        "candidate_count": 1,
        "legal_plan_count": 1 if allowed_plan_id else 0,
        "valid_candidate_counts": {
            "proposition_support": 1 if allowed_plan_id else 0,
            "explicit_contradiction": 0,
        },
        "best_rejected_candidate": None,
        "best_rejected_candidates": {},
        "reason": "" if allowed_plan_id else "candidate_not_answerable",
        "required_slots": ["actor", "predicate", "object"],
        "covered_slots": covered,
        "required_tokens": ["method"],
        "covered_tokens": ["method"] if selected_plan_id else [],
        "required_object_tokens": ["method"],
        "covered_object_tokens": ["method"] if selected_plan_id else [],
        "event_ids": [event_id],
        "selected_plan_id": selected_plan_id,
        "enumeration_policy_complete": True,
        **_debug_plan_digest_fields(selector_ref),
        "relation_analysis_count": 2,
        "candidate_decisions_complete": True,
        "candidate_decision_count": 2,
        "candidate_decisions_digest": _fixture_digest(decisions),
        "candidate_decisions": decisions,
    }


def _debug_selector_projection_trace(
    contract_id: str,
    *,
    input_key: str,
) -> dict[str, Any]:
    decisions = [
        {
            "selector_id": "E1:S1",
            "selected": True,
            "decision": "selected_without_limit",
        }
    ]
    return {
        "contract_id": contract_id,
        "complete": True,
        input_key: 1,
        "selected_selector_count": 1,
        "decision_count": 1,
        "decisions_digest": _fixture_digest(decisions),
        "decisions": decisions,
    }


def _debug_selector_crosswalk() -> dict[str, Any]:
    payload = {
        "contract_id": "qasper_selector_crosswalk.v1",
        "complete": True,
        "source_selector_count": 1,
        "canonical_selector_count": 1,
        "mapped_canonical_selector_count": 1,
        "source_selectors": [
            {
                "source_selector_ref": "E1:S1",
                "canonical_selector_refs": ["E1:S1"],
            }
        ],
        "canonical_selectors": [
            {
                "canonical_selector_ref": "E1:S1",
                "source_selector_refs": ["E1:S1"],
                "mapped": True,
            }
        ],
    }
    return {**payload, "crosswalk_digest": _fixture_digest(payload)}


def _debug_plan_digest_fields(selector_ref: str) -> dict[str, Any]:
    enumeration_policy = {
        "local": {"complete": True},
        "cross_event": {"complete": True},
    }
    selector_pool_decisions = [
        {
            "selector_ref": selector_ref,
            "selected": True,
            "decision": "selected_for_candidate_enumeration",
        }
    ]
    return {
        "enumeration_policy_digest": _fixture_digest(enumeration_policy),
        "enumeration_policy": enumeration_policy,
        "selector_pool_decisions_complete": True,
        "selector_pool_decision_count": len(selector_pool_decisions),
        "selector_pool_decisions_digest": _fixture_digest(selector_pool_decisions),
        "selector_pool_decisions": selector_pool_decisions,
    }


def _debug_first_decisive_transition(
    *,
    audit_status: str,
    legal_plan_count: int,
    candidate: str,
) -> dict[str, Any]:
    if legal_plan_count == 0:
        stage, decision = "plan_construction", "no_legal_evidence_plan"
    elif candidate == "unanswerable":
        stage, decision = (
            "candidate_generation",
            "unanswerable_despite_legal_local_plan",
        )
    elif audit_status == "failed":
        stage, decision = "auditor_semantics", "fixture_audit"
    elif audit_status == "candidate_bound":
        stage, decision = "auditor_semantics", "candidate_bound"
    else:
        stage, decision = "terminal_semantic_commit", "accepted"
    context = {
        "stage": stage,
        "decision": decision,
        "candidate": candidate,
        "legal_plan_count": legal_plan_count,
        "audit_status": audit_status,
    }
    return {
        "stage": stage,
        "decision": decision,
        "candidate": candidate,
        "decision_context": context,
        "decision_context_digest": _fixture_digest(context),
        "observation_digest": _fixture_digest(context),
    }


def _debug_plan_selection_raw(relation: str, plan_id: str) -> str:
    return json.dumps(
        {
            "candidate_judgment": relation,
            "canonical_evidence_plan_id": plan_id,
        },
        separators=(",", ":"),
    )


def _raw_response_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
