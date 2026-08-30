from __future__ import annotations

import hashlib
import json
from typing import Any

from benchmark.tests.contract_smoke_fixtures import _fixture_digest


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
) -> dict[str, Any]:
    plan_id = (
        ""
        if relation == "unknown"
        else _fixture_digest({"canonical_plan": transaction_id})
    )
    return {
        "debug_trace": _debug_semantic_trace(
            candidate,
            relation,
            audit_status,
            typed_conclusion,
            conclusion_audit,
            plan_id=plan_id,
        ),
        "semantic_data_lineage": _debug_semantic_data_lineage(
            relation,
            audit_status,
            pack_identity,
            plan_id=plan_id,
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
    relation: str,
    audit_status: str,
    pack_identity: dict[str, str],
    *,
    plan_id: str,
) -> dict[str, Any]:
    proposal_raw = _debug_plan_selection_raw(relation, plan_id)
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
            "allowed_plan_ids": [plan_id] if plan_id else [],
            "response_schema_digest": _fixture_digest(
                {"schema": "canonical_plan_selection", "plan_id": plan_id}
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
            "selected_plan_id": plan_id,
        },
        **_debug_lineage_plan_fields(pack_identity, plan_id),
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
    }


def _debug_lineage_plan_fields(
    pack_identity: dict[str, str],
    plan_id: str,
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
            plan_id,
            selector_ref=selector_ref,
            event_id=event_id,
        ),
    }


def _debug_source_packing(pack_identity: dict[str, str]) -> dict[str, Any]:
    text = "The paper uses the method."
    return {
        "status": "passed",
        "contract_id": "qasper_source_packing_observation.v1",
        "semantic_pack_digest": pack_identity["semantic_pack_digest"],
        "source_semantic_pack_digest": pack_identity["semantic_pack_digest"],
        "source_records": [
            {
                "evidence_id": "span:paper:s1",
                "text_digest": hashlib.sha256(text.encode("utf-8")).hexdigest(),
                "semantic_rank": 1,
                "selected_for_windowing": True,
                "packed": True,
                "stop_stage": "packed",
            }
        ],
        "records": [
            {
                "evidence_id": "span:paper:s1",
                "text_digest": _fixture_digest(text),
                "selector_refs": ["E1:S1"],
            }
        ],
        "dropped_count": 0,
        "truncated_count": 0,
    }


def _debug_plan_construction(
    plan_id: str,
    *,
    selector_ref: str,
    event_id: str,
) -> dict[str, Any]:
    covered = ["actor", "predicate", "object"] if plan_id else []
    return {
        "status": "passed",
        "transport_status": "passed",
        "semantic_plan_status": "passed" if plan_id else "not_applicable",
        "universe": [selector_ref],
        "universe_refs": [selector_ref],
        "candidate_count": 1,
        "legal_plan_count": 1 if plan_id else 0,
        "valid_candidate_counts": {
            "proposition_support": 1 if plan_id else 0,
            "explicit_contradiction": 0,
        },
        "best_rejected_candidate": None,
        "best_rejected_candidates": {},
        "reason": "" if plan_id else "candidate_not_answerable",
        "required_slots": ["actor", "predicate", "object"],
        "covered_slots": covered,
        "required_tokens": ["method"],
        "covered_tokens": ["method"] if plan_id else [],
        "required_object_tokens": ["method"],
        "covered_object_tokens": ["method"] if plan_id else [],
        "event_ids": [event_id],
        "selected_plan_id": plan_id,
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
