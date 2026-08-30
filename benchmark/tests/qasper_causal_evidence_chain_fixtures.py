from __future__ import annotations

from typing import Any

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest


def causal_row(*, ambiguous: bool, candidate: str, legal_plan_count: int) -> dict:
    legal_plan_id = "6" * 64 if legal_plan_count else ""
    transition_stage = (
        "candidate_generation"
        if candidate == "unanswerable" and legal_plan_count
        else "plan_construction"
    )
    transition_decision = (
        "unanswerable_despite_legal_local_plan"
        if transition_stage == "candidate_generation"
        else "no_legal_evidence_plan"
    )
    return {
        **_terminal_fields(),
        "qasper_annotation_diagnostics": {"ambiguous": ambiguous},
        "recovery_events": _recovery_events(),
        "candidate_input_state_observation": _candidate_input_state(),
        "main_candidate_generator": _generator_fields(
            candidate,
            legal_plan_count,
            legal_plan_id,
        ),
        "semantic_verifier": _verifier_fields(
            candidate,
            legal_plan_count,
            legal_plan_id,
            transition_stage,
            transition_decision,
        ),
    }


def _terminal_fields() -> dict[str, Any]:
    return {
        "example_id": "example-1",
        "route": "text_rag",
        "answer_status": "abstained",
        "terminal_outcome": "safe_abstention",
        "terminal_semantic_commit": {
            "contract_id": "terminal_semantic_commit.v3",
            "semantic_answer": "unanswerable",
            "outcome": "safe_abstention",
            "answer_status": "abstained",
            "projection_hash": "e" * 64,
        },
    }


def _recovery_events() -> list[dict[str, str]]:
    return [
        {
            "stage": "targeted_retrieval",
            "recovery_action": "stop_without_reverify",
            "recovery_outcome": "no_progress",
        }
    ]


def _generator_fields(
    candidate: str,
    legal_plan_count: int,
    legal_plan_id: str,
) -> dict[str, Any]:
    context = _model_decision_context(
        candidate,
        legal_plan_count,
        _plan_candidate_decisions(legal_plan_count),
    )
    return {
        "status": "parsed",
        "typed_candidate": candidate,
        "raw_response_digest": "9" * 64,
        "input_digest": "a" * 64,
        "output_digest": "b" * 64,
        "model_decision": _model_decision(candidate, context),
        "candidate_evidence_set_binding": _candidate_binding(
            legal_plan_count,
            legal_plan_id,
        ),
        "candidate_prompt_projection_trace": _record_projection(
            "qasper_candidate_prompt_projection.v1"
        ),
        "candidate_request_projection_trace": _record_projection(
            "qasper_candidate_request_projection.v1"
        ),
        "canonical_selector_projection_trace": _canonical_selector_projection(),
    }


def _model_decision_context(
    candidate: str,
    legal_plan_count: int,
    decisions: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "decision_plan_alignment": (
            "conflicts_with_legal_local_plan"
            if legal_plan_count
            else "aligned_no_legal_local_plan"
        ),
        "plan_candidate_decisions_digest": canonical_digest(decisions),
        "typed_candidate": candidate,
        "required_slot_count": 1,
        "legal_plan_count": legal_plan_count,
    }


def _model_decision(
    candidate: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    return {
        "contract_id": "qasper_model_candidate_decision.v1",
        "status": "parsed",
        "decision": candidate,
        "decision_origin": "model_output",
        "rationale_status": "not_requested_by_low_entropy_contract",
        "decision_context": context,
        "decision_context_digest": canonical_digest(context),
        "raw_response_digest": "9" * 64,
    }


def _candidate_binding(
    legal_plan_count: int,
    legal_plan_id: str,
) -> dict[str, Any]:
    return {
        "binding_state": "relation_bound_support" if legal_plan_count else "unresolved",
        "canonical_evidence_plan": {
            "contract_id": "canonical_proposition_evidence_plan.v2",
            "plan_id": "7" * 64,
            "support_plan": {"plan_id": legal_plan_id} if legal_plan_count else None,
            "contradiction_plan": None,
        },
    }


def _canonical_selector_projection() -> dict[str, Any]:
    decisions = [
        {"decision": "selected", "reason": "selected_for_canonical_selector_universe"}
    ]
    return {
        "contract_id": "qasper_canonical_selector_projection.v1",
        "complete": True,
        "input_selector_count": 1,
        "decision_count": 1,
        "decisions_digest": canonical_digest(decisions),
        "decisions": decisions,
    }


def _verifier_fields(
    candidate: str,
    legal_plan_count: int,
    legal_plan_id: str,
    transition_stage: str,
    transition_decision: str,
) -> dict[str, Any]:
    return {
        "audit_status": "candidate_bound",
        "audit_reason": "unknown_gap_audited",
        "semantic_data_lineage": _lineage_fields(
            candidate,
            legal_plan_count,
            legal_plan_id,
            transition_stage,
            transition_decision,
        ),
    }


def _lineage_fields(
    candidate: str,
    legal_plan_count: int,
    legal_plan_id: str,
    transition_stage: str,
    transition_decision: str,
) -> dict[str, Any]:
    return {
        "source_packing": _source_packing(),
        "selector": {"universe_refs": ["E1:S1"]},
        "proposal_contract": {
            "allowed_plan_ids": [legal_plan_id] if legal_plan_id else []
        },
        "local_projection": {
            "status": "not_run" if not legal_plan_count else "passed",
            "selected_plan_id": "",
        },
        "plan_construction": _plan_construction(legal_plan_count),
        "proposal_attempts": _attempts("d" * 64),
        "audit": {"status": "parsed", "attempts": _attempts("e" * 64)},
        "first_decisive_transition": _first_transition(
            candidate,
            legal_plan_count,
            transition_stage,
            transition_decision,
        ),
    }


def _source_packing() -> dict[str, Any]:
    source_decisions = [
        {
            "source_item_index": 1,
            "evidence_id": "evidence-1",
            "text_digest": "1" * 64,
            "text_chars": 10,
            "decision": "packed",
            "reason": "packed",
            "semantic_rank": 1,
            "priority": [0, 0],
            "priority_factors": {"ranked_position": 0},
        }
    ]
    window_decisions = [
        {
            "stage": "window_selection",
            "selected": True,
            "reason": "full_source_within_limit",
        },
        {
            "stage": "fit_to_input_budget",
            "selected": True,
            "reason": "accepted_with_primary_window",
        },
    ]
    crosswalk = _crosswalk()
    return {
        "contract_id": "qasper_source_packing_observation.v1",
        "status": "passed",
        "source_input_snapshot": _source_input_snapshot(),
        "source_decisions_complete": True,
        "source_input_count": 1,
        "source_decision_count": 1,
        "source_decisions_digest": canonical_digest(source_decisions),
        "source_decisions": source_decisions,
        "window_decisions_complete": True,
        "window_selection_decision_count": 1,
        "selected_window_count": 1,
        "window_fit_decision_count": 1,
        "window_decision_count": 2,
        "window_decisions_digest": canonical_digest(window_decisions),
        "window_decisions": window_decisions,
        "records": [
            {
                "evidence_id": "evidence-1",
                "selector_refs": ["E1:S1"],
                "source_selector_projection_trace": _selector_projection(
                    "canonical_span_selector_projection.v1",
                    "input_span_count",
                ),
            }
        ],
        "canonical_records": [
            {
                "evidence_id": "evidence-1",
                "selector_refs": ["E1:S1"],
                "candidate_selector_projection_trace": _selector_projection(
                    "qasper_candidate_selector_projection.v1",
                    "input_selector_count",
                ),
            }
        ],
        "selector_crosswalk": crosswalk,
    }


def _source_input_snapshot() -> dict[str, Any]:
    source_items = [
        {
            "source_item_index": 1,
            "evidence_id": "evidence-1",
            "text_digest": "1" * 64,
            "text_chars": 10,
            "identity_decision": "eligible",
            "identity_reason": "accepted_for_semantic_ranking",
        }
    ]
    ranked = [{"ranked_position": 0, "canonical_id": "evidence-1"}]
    slots = [{"slot_id": "support:boolean_proposition"}]
    query_plan = {"plan_id": "plan-1"}
    payload = {
        "contract_id": "semantic_source_input_snapshot.v1",
        "complete": True,
        "route": "text_rag",
        "candidate_priority": True,
        "question": "Did the authors compare the systems?",
        "question_digest": canonical_digest("Did the authors compare the systems?"),
        "query_plan": query_plan,
        "query_plan_digest": canonical_digest(query_plan),
        "required_slots": slots,
        "required_slots_digest": canonical_digest(slots),
        "max_context_length": None,
        "item_char_limit": 2000,
        "source_item_count": 1,
        "source_items_digest": canonical_digest(source_items),
        "source_items": source_items,
        "ranked_evidence_present": True,
        "ranked_evidence_count": 1,
        "ranked_evidence_digest": canonical_digest(ranked),
        "ranked_evidence": ranked,
    }
    payload["snapshot_digest"] = canonical_digest(payload)
    return payload


def _candidate_input_state() -> dict[str, Any]:
    ranked = [{"ranked_position": 0, "canonical_id": "evidence-1"}]
    payload = {
        "contract_id": "qasper_candidate_input_state_observation.v1",
        "complete": True,
        "status": "preserved",
        "stage_ranked_evidence_present": True,
        "stage_ranked_evidence_count": 1,
        "stage_ranked_evidence_digest": canonical_digest(ranked),
        "stage_ranked_evidence": ranked,
        "terminal_ranked_evidence_present": True,
        "terminal_ranked_evidence_count": 1,
        "terminal_ranked_evidence_digest": canonical_digest(ranked),
        "terminal_ranked_evidence": ranked,
        "first_divergence": {},
        "added_after_candidate": [],
        "removed_after_candidate": [],
        "source_input_snapshot_digest": _source_input_snapshot()["snapshot_digest"],
    }
    payload["observation_digest"] = canonical_digest(payload)
    return payload


def _selector_projection(contract_id: str, input_key: str) -> dict[str, Any]:
    decisions = [{"decision": "selected_without_limit"}]
    return {
        "contract_id": contract_id,
        "complete": True,
        "decision_count": 1,
        input_key: 1,
        "decisions_digest": canonical_digest(decisions),
        "decisions": decisions,
    }


def _crosswalk() -> dict[str, Any]:
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
    return {**payload, "crosswalk_digest": canonical_digest(payload)}


def _plan_construction(legal_plan_count: int) -> dict[str, Any]:
    decisions = _plan_candidate_decisions(legal_plan_count)
    enumeration_policy = {
        "local": {"complete": True},
        "cross_event": {"complete": True},
    }
    selector_decisions = [
        {"selector_ref": "E1:S1", "decision": "selected_for_candidate_enumeration"}
    ]
    return {
        "status": "passed",
        "transport_status": "passed",
        "semantic_plan_status": "passed" if legal_plan_count else "not_applicable",
        "universe": ["E1:S1"],
        "universe_refs": ["E1:S1"],
        "legal_plan_count": legal_plan_count,
        "candidate_count": 1,
        "valid_candidate_counts": {
            "proposition_support": 1 if legal_plan_count else 0,
            "explicit_contradiction": 0,
        },
        "best_rejected_candidate": None,
        "best_rejected_candidates": {},
        "reason": "" if legal_plan_count else "candidate_not_answerable",
        "required_slots": ["actor", "predicate", "object"],
        "covered_slots": (["actor", "predicate", "object"] if legal_plan_count else []),
        "required_tokens": ["method"],
        "covered_tokens": ["method"] if legal_plan_count else [],
        "required_object_tokens": ["method"],
        "covered_object_tokens": ["method"] if legal_plan_count else [],
        "event_ids": ["fixture-event"],
        "candidate_decision_count": 2,
        "relation_analysis_count": 2,
        "candidate_decisions_complete": True,
        "enumeration_policy_complete": True,
        "enumeration_policy_digest": canonical_digest(enumeration_policy),
        "enumeration_policy": enumeration_policy,
        "selector_pool_decisions_complete": True,
        "selector_pool_decision_count": 1,
        "selector_pool_decisions_digest": canonical_digest(selector_decisions),
        "selector_pool_decisions": selector_decisions,
        "candidate_decisions_digest": canonical_digest(decisions),
        "candidate_decisions": decisions,
        "selected_plan_id": "",
    }


def _plan_candidate_decisions(legal_plan_count: int) -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": "support",
            "relation": "proposition_support",
            "origin": "event_local",
            "decision": "accepted" if legal_plan_count else "rejected",
            "rejection_reasons": [] if legal_plan_count else ["fixture_rejection"],
        },
        {
            "candidate_id": "contradiction",
            "relation": "explicit_contradiction",
            "origin": "event_local",
            "decision": "rejected",
            "rejection_reasons": ["fixture_rejection"],
        },
    ]


def _attempts(raw_response_digest: str) -> list[dict[str, Any]]:
    return [
        {
            "attempt": 1,
            "raw_response_digest": raw_response_digest,
            "parse_failure_reason": "",
            "provider_failure_reason": "",
        }
    ]


def _first_transition(
    candidate: str,
    legal_plan_count: int,
    stage: str,
    decision: str,
) -> dict[str, Any]:
    context = {
        "candidate": candidate,
        "candidate_decision_count": 2,
        "legal_plan_count": legal_plan_count,
    }
    return {
        "stage": stage,
        "decision": decision,
        "candidate": candidate,
        "decision_context": context,
        "decision_context_digest": canonical_digest(context),
        "observation_digest": "f" * 64,
    }


def _record_projection(contract_id: str) -> dict[str, Any]:
    decisions = [{"decision": "selected"}]
    attempts = [{"decision": "accepted"}]
    return {
        "contract_id": contract_id,
        "complete": True,
        "input_record_count": 1,
        "decision_count": 1,
        "decisions_digest": canonical_digest(decisions),
        "decisions": decisions,
        "attempt_count": 1,
        "attempts_digest": canonical_digest(attempts),
        "attempts": attempts,
    }
