from __future__ import annotations

import json
from typing import Any

from benchmark.tests.contract_smoke_fixtures import _fixture_digest, _prediction
from benchmark.tests.qasper_debug_semantic_pack_fixtures import (
    _debug_audited_premises,
    _debug_semantic_authority,
    _debug_semantic_pack,
    _debug_semantic_pack_identity,
)


def _qasper_debug_prediction(
    example_id: str,
    route: str,
    *,
    state: tuple[str, str, bool] | None = None,
    candidate: str | None = None,
) -> dict[str, Any]:
    prediction = _prediction([])
    group_id = f"group:{example_id}"
    example_index = int(example_id.rsplit("-", 1)[-1])
    case = _debug_case_fields(example_index) if state is None else _state_case(state)
    if candidate is not None:
        case = {**case, "candidate": candidate}
    candidate = str(case["candidate"])
    relation = str(case["relation"])
    audit_status = str(case["audit_status"])
    terminal_answer = str(case["terminal_answer"])
    terminal_outcome = str(case["terminal_outcome"])
    gold = case["gold"]
    ambiguous = case["ambiguous"]
    metadata = prediction["evidence_metadata"]
    _populate_debug_semantic_metadata(
        metadata,
        example_id,
        route,
        group_id,
        candidate,
        relation,
        audit_status,
    )
    prediction.update(
        {
            "example_id": example_id,
            "route": route,
            "answer_type": "boolean",
            "gold_answers": gold,
            "predicted_answer": terminal_answer,
            "answer_for_scoring": terminal_answer,
            "controller_trace": [
                {
                    "stage": "claim_aggregation",
                    "input_text": "yes",
                    "output_text": "yes",
                    "input_digest": "claim-input",
                    "output_digest": "claim-output",
                }
            ],
            **_debug_annotation_fields(
                example_id, candidate, terminal_answer, ambiguous
            ),
            "terminal_outcome": terminal_outcome,
            "terminal_outcome_reason": "",
            "terminal_outcome_contract_violation": False,
            "terminal_semantic_commit": {
                "contract_id": "terminal_semantic_commit.v3",
                "semantic_answer": terminal_answer,
                "outcome": terminal_outcome,
            },
        }
    )
    return prediction


def _populate_debug_semantic_metadata(
    metadata: dict[str, Any],
    example_id: str,
    route: str,
    group_id: str,
    candidate: str,
    relation: str,
    audit_status: str,
) -> None:
    generator = _debug_generator_trace(example_id, route, group_id, candidate)
    semantic_pack = _debug_semantic_pack(str(generator["transaction_id"]))
    identity = _debug_semantic_pack_identity(semantic_pack)
    generator.update(
        canonical_semantic_pack_digest=identity["semantic_pack_digest"],
        canonical_span_universe_digest=identity["span_universe_digest"],
        canonical_pack_candidate_transaction_id=identity["candidate_transaction_id"],
    )
    metadata.update(
        qasper_canonical_semantic_pack=semantic_pack,
        qasper_candidate_generation=generator,
        semantic_proposition_verifier=_debug_verifier_trace(
            example_id,
            route,
            group_id,
            candidate,
            relation,
            audit_status,
            identity,
        ),
    )
    if relation in {"supported", "contradicted"} and audit_status == "passed":
        metadata["semantic_proposition_authority"] = _debug_semantic_authority(
            _debug_verifier_verdict(candidate, relation),
            identity,
        )


def _qasper_contract_probe_predictions() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    states = [
        (judgment, auditor_status, ambiguous)
        for judgment in ("supported", "contradicted", "unknown")
        for auditor_status in ("passed", "failed")
        for ambiguous in (False, True)
    ]
    for index, state in enumerate(states, start=1):
        for route in ("controller_auto", "crag_guarded", "hybrid_rag"):
            row = _qasper_debug_prediction(
                f"probe-{index}",
                route,
                state=state,
                candidate="no" if index == 1 else "yes",
            )
            row["qasper_debug_lane"] = "contract_probe"
            rows.append(row)
    return rows


def _debug_annotation_fields(
    example_id: str,
    candidate: str,
    terminal_answer: str,
    ambiguous: bool,
) -> dict[str, Any]:
    annotation_id = f"annotation:{example_id}"
    return {
        "example_metadata": {
            "qasper_answer_annotations": [
                {"annotation_id": annotation_id, "yes_no": candidate == "yes"}
            ]
        },
        "qasper_annotation_scores": [
            {
                "contract_id": "qasper_annotation_score.v1",
                "annotation_index": 1,
                "annotation_id": annotation_id,
                "answer_f1": 1.0 if terminal_answer == "yes" else 0.0,
                "typed_accuracy": 1.0,
                "evidence_f1": 1.0,
                "ambiguity_marker": "ambiguous" if ambiguous else "",
            }
        ],
        "qasper_annotation_diagnostics": {
            "contract_id": "qasper_annotation_diagnostics.v1",
            "annotation_count": 1,
            "ambiguous": ambiguous,
            "ambiguity_reasons": ["fixture_ambiguous"] if ambiguous else [],
            "canonical_answer_classes": [[candidate if not ambiguous else "yes"]],
        },
    }


def _debug_case_fields(example_index: int) -> dict[str, Any]:
    if example_index in {1, 2, 6}:
        return {
            "candidate": "yes",
            "relation": "supported",
            "audit_status": "passed",
            "terminal_answer": "yes",
            "terminal_outcome": "answered",
            "gold": ["yes"],
            "ambiguous": False,
        }
    if example_index == 3:
        relation = "contradicted"
    elif example_index == 4:
        relation = "unknown"
    else:
        relation = "unknown"
    return {
        "candidate": "no" if example_index in {3, 5} else "yes",
        "relation": relation,
        "audit_status": "failed" if example_index == 5 else "passed",
        "terminal_answer": "unanswerable",
        "terminal_outcome": "safe_abstention",
        "gold": ["unanswerable"],
        "ambiguous": True,
    }


def _state_case(state: tuple[str, str, bool]) -> dict[str, Any]:
    relation, audit_status, ambiguous = state
    candidate = "no" if relation == "supported" and not ambiguous else "yes"
    terminal_answer = (
        candidate
        if relation == "supported" and audit_status == "passed"
        else "unanswerable"
    )
    return {
        "candidate": candidate,
        "relation": relation,
        "audit_status": audit_status,
        "terminal_answer": terminal_answer,
        "terminal_outcome": "answered"
        if terminal_answer != "unanswerable"
        else "safe_abstention",
        "gold": [terminal_answer],
        "ambiguous": ambiguous,
    }


def _debug_generator_trace(
    example_id: str,
    route: str,
    group_id: str,
    candidate: str,
) -> dict[str, Any]:
    transaction_id = f"generator:{example_id}:{route}"
    raw_response = json.dumps(
        {"candidate": candidate}, ensure_ascii=False, separators=(",", ":")
    )
    raw_digest = _fixture_digest(raw_response)
    candidate_digest = _fixture_digest(candidate)
    output_digest = _fixture_digest(
        {
            "raw_response_digest": raw_digest,
            "provider_output_digest": raw_digest,
            "cleaned_response_digest": raw_digest,
            "raw_candidate": candidate,
            "raw_candidate_digest": candidate_digest,
            "typed_candidate": candidate,
            "typed_candidate_digest": candidate_digest,
            "raw_candidate_identity_preserved": True,
            "status": "parsed",
            "failure_reason": "",
            "finish_reason": "stop",
        }
    )
    return {
        "contract_id": "qasper_typed_candidate_generation.v2",
        "status": "parsed",
        "model": "Qwen/Qwen3-8B",
        "message_stack": [
            {"index": 0, "role": "system", "content": "verify"},
            {"index": 1, "role": "user", "content": "question"},
        ],
        "raw_response": raw_response,
        "raw_response_digest": raw_digest,
        "provider_output_digest": raw_digest,
        "raw_response_truncated": False,
        "cleaned_response": raw_response,
        "raw_candidate": candidate,
        "raw_candidate_failure_reason": "",
        "raw_candidate_digest": candidate_digest,
        "typed_candidate": candidate,
        "typed_candidate_digest": candidate_digest,
        "raw_candidate_identity_preserved": True,
        "typed_proposition": {
            "actor": "current_paper",
            "predicate": "use",
            "object_surface": "the method",
            "quantifier": "none",
        },
        "question_proposition_resolution": {"status": "complete"},
        "required_slots": [
            {
                "slot_id": "support:boolean_proposition",
                "binding_status": "bound",
                "evidence_ids": ["span:paper:s1"],
                "evidence_refs": ["E1:S1"],
            }
        ],
        "finish_reason": "stop",
        "failure_reason": "",
        **_debug_generator_lineage(
            candidate,
            raw_response,
            raw_digest,
            candidate_digest,
            output_digest,
            transaction_id,
        ),
        "trace_group_id": group_id,
        "transaction_id": transaction_id,
        "attempt_id": f"{transaction_id}:1",
        "effective_seed": 20260724,
        "input_digest": f"generator-input:{route}",
        "output_digest": output_digest,
    }


def _debug_generator_lineage(
    candidate: str,
    raw_response: str,
    raw_digest: str,
    candidate_digest: str,
    output_digest: str,
    transaction_id: str,
) -> dict[str, Any]:
    return {
        "transformation_stages": [
            {
                "stage": "raw_response",
                "value": raw_response,
                "digest": raw_digest,
                "failure_reason": "",
            },
            {
                "stage": "cleaning",
                "value": raw_response,
                "digest": raw_digest,
                "changed": False,
                "failure_reason": "",
            },
            {
                "stage": "typed_candidate",
                "value": candidate,
                "digest": candidate_digest,
                "failure_reason": "",
                "source_stage": "cleaning",
                "identity_preserved": True,
            },
        ],
        "attempts": [
            {
                "attempt_id": f"{transaction_id}:1",
                "status": "parsed",
                "failure_reason": "",
                "raw_response": raw_response,
                "cleaned_response": raw_response,
                "raw_candidate": candidate,
                "raw_candidate_digest": candidate_digest,
                "typed_candidate": candidate,
                "typed_candidate_digest": candidate_digest,
                "raw_candidate_identity_preserved": True,
                "finish_reason": "stop",
                "output_digest": output_digest,
            }
        ],
    }


def _debug_verifier_trace(
    example_id: str,
    route: str,
    group_id: str,
    candidate: str,
    relation: str,
    audit_status: str,
    pack_identity: dict[str, str],
) -> dict[str, Any]:
    transaction_id = f"verifier:{example_id}:{route}"
    verdict = _debug_verifier_verdict(candidate, relation)
    typed_conclusion, conclusion_audit, candidate_audit = _debug_verifier_payload(
        example_id,
        candidate,
        relation,
        audit_status,
        pack_identity,
    )
    safe_terminal = relation != "supported"
    return {
        "contract_id": "semantic_proposition_verifier_runtime.v3",
        "status": "parsed",
        "model": "Qwen/Qwen3-8B",
        "candidate_label": candidate,
        "candidate_verification_status": relation,
        "verdict": verdict,
        "replacement_candidate_allowed": False,
        "explicit_contradiction": verdict == "no",
        "candidate_verifier_disagreement": relation == "contradicted",
        "unknown": relation == "unknown",
        "proposal_model_call_count": 1,
        "audit_model_call_count": 1,
        "candidate_verification_audit": candidate_audit,
        "question_proposition": {"quantifier": "none"},
        "typed_conclusion": typed_conclusion,
        "conclusion_audit": conclusion_audit,
        "proposal_contract": "semantic_proposition_verdict.v4",
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
        "audit_reason": "fixture_audit",
        "evidence_label_map": {"E1": "span:paper:s1"},
        "unknown_assessment": _debug_unknown_assessment(relation),
        "semantic_pack_digest": pack_identity["semantic_pack_digest"],
        "canonical_span_universe_digest": pack_identity["span_universe_digest"],
        "candidate_transaction_id": pack_identity["candidate_transaction_id"],
        "canonical_pack_continuity_status": "preserved",
        "auditor_semantic_pack_identity": pack_identity,
        "required_slot_ids": ["support:boolean_proposition"]
        if relation == "supported"
        else [],
        "verified_support_slot_ids": ["support:boolean_proposition"]
        if relation == "supported"
        else [],
        "raw_candidate_digest": _fixture_digest(candidate),
        "typed_candidate_digest": _fixture_digest(candidate),
        "verifier_input_candidate_digest": _fixture_digest(candidate),
        "candidate_raw_identity_preserved": True,
        "debug_trace": _debug_semantic_trace(
            candidate, relation, audit_status, typed_conclusion, conclusion_audit
        ),
        "trace_group_id": group_id,
        "transaction_id": transaction_id,
        "attempt_id": f"{transaction_id}:proposal:1",
        "auditor_attempt_id": f"{transaction_id}:auditor:1",
        "effective_seed": 20260724,
        "input_digest": f"verifier-input:{route}",
        "output_digest": f"verifier-output:{route}",
    }


def _debug_verifier_payload(
    example_id: str,
    candidate: str,
    relation: str,
    audit_status: str,
    pack_identity: dict[str, str],
) -> tuple[dict[str, Any], dict[str, str], dict[str, Any]]:
    typed_conclusion = {
        "contract_id": "typed_conclusion.v1",
        "conclusion_id": f"conclusion:{example_id}",
        "polarity": candidate,
    }
    conclusion_audit = {"contract_id": "conclusion_audit.v2"}
    candidate_audit = _debug_candidate_audit(
        candidate,
        relation,
        audit_status,
        typed_conclusion,
        semantic_pack_identity=pack_identity,
    )
    return typed_conclusion, conclusion_audit, candidate_audit


def _debug_verifier_verdict(candidate: str, relation: str) -> str:
    if relation == "unknown":
        return "insufficient_evidence"
    if candidate == "unanswerable":
        return "yes"
    if relation == "supported":
        return candidate
    return "no" if candidate == "yes" else "yes"


def _debug_candidate_audit(
    candidate: str,
    relation: str,
    audit_status: str,
    typed_conclusion: dict[str, Any],
    *,
    semantic_pack_identity: dict[str, str] | None = None,
) -> dict[str, Any]:
    audit = {
        "contract_id": "candidate_verifier_audit.v2",
        "status": audit_status,
        "mode": "candidate_bound_audit",
        "audited_candidate": candidate,
        "audited_judgment": relation,
        "reason": "fixture_audit",
        "replacement_candidate_allowed": False,
        "semantic_pack_identity": dict(semantic_pack_identity or {}),
    }
    if relation == "supported":
        audit.update(
            {
                "classification": "supported",
                "audited_verdict": candidate,
            }
        )
    elif relation == "contradicted":
        audit.update(
            {
                "classification": "explicit_contradiction",
                "audited_verdict": "no" if candidate == "yes" else "yes",
            }
        )
    else:
        premises = _debug_audited_premises()
        audit.update(
            {
                "mode": "candidate_bound_unknown_audit",
                "reason": "unknown_gap_audited",
                "classification": "unknown",
                "audit_scope": "original_candidate_and_verifier_unknown_only",
                "audited_verdict": "insufficient_evidence",
                "audited_typed_conclusion": typed_conclusion,
                "audited_premises": premises,
                "audited_premise_digest": _fixture_digest(premises),
                "reviewed_evidence_ids": ["span:paper:s1"],
                "unresolved_proposition_slots": ["support:boolean_proposition"],
                "support_gap": "fixture_support_gap",
                "contradiction_gap": "fixture_contradiction_gap",
            }
        )
    return audit


def _debug_unknown_assessment(relation: str) -> dict[str, Any]:
    if relation != "unknown":
        return {}
    return {
        "reviewed_evidence": _debug_audited_premises(),
        "unresolved_proposition_slots": ["support:boolean_proposition"],
        "support_gap": "fixture_support_gap",
        "contradiction_gap": "fixture_contradiction_gap",
    }


def _debug_semantic_trace(
    candidate: str,
    relation: str,
    audit_status: str,
    typed_conclusion: dict[str, Any],
    conclusion_audit: dict[str, Any],
) -> dict[str, Any]:
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
                                "raw_response": json.dumps(
                                    {"verdict": candidate}, separators=(",", ":")
                                ),
                                "finish_reason": "stop",
                                "parse_failure_reason": "",
                                "provider_failure_reason": "",
                                "parsed_value": {
                                    "contract_id": "semantic_proposition_verdict.v4",
                                    "verdict": candidate,
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
                                "raw_response": '{"status":"verified"}',
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
