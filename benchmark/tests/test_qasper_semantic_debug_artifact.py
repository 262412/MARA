from __future__ import annotations

from benchmark.qasper_semantic_debug_artifact import (
    qasper_semantic_debug_rows,
    qasper_semantic_debug_summary,
)


def _prediction() -> dict:
    return {
        "example_id": "example-1",
        "route": "text_rag",
        "question": "Did the authors use the method?",
        "gold_answers": ["no"],
        "predicted_answer": "unanswerable",
        "answer_status": "abstained",
        "terminal_outcome": "safe_abstention",
        "terminal_outcome_reason": "Strict verification requested.",
        "failure_taxonomy": "false_abstention",
        "engine_terminal_evidence_bundle": {
            "route": "doc_text",
            "items": [],
            "metadata": _semantic_metadata(),
        },
        "engine_terminal_state": {
            "typed_authority": {
                "state": "missing",
                "reason": "retrieval_evidence_insufficient",
            }
        },
        "controller_trace": _recovery_trace(),
    }


def _semantic_metadata() -> dict:
    return {
        "semantic_proposition_verifier": {
            "contract_id": "semantic_proposition_verifier_runtime.v2",
            "status": "parsed",
            "reason": "strict_schema_and_entailment_audit",
            "audit_status": "verified",
            "conclusion_audit": {
                "contract_id": "conclusion_audit.v1",
                "conclusion_entailed": True,
                "polarity_consistent": True,
                "quantifier_consistent": True,
                "scope_consistent": True,
            },
            "debug_trace": {
                "contract_id": "semantic_proposition_debug_trace.v2",
                "events": [
                    {
                        "event_index": 1,
                        "event": "model_transaction",
                        "cache_key": "signature",
                        "auditor_relationship": "same_instance",
                        "outcome": {"audit_status": "verified"},
                    }
                ],
            },
        },
        "semantic_proposition_authority": {
            "contract_id": "semantic_proposition_verdict.v3",
            "status": "rejected",
            "reason": "semantic_premise_fragment_invalid",
            "debug_trace": {
                "contract_id": "semantic_proposition_authority_debug.v1",
                "attempts": [],
            },
        },
        "query_plan": {
            "evidence_slots": [
                {
                    "slot_id": "support:boolean_proposition",
                    "required_for_verification": True,
                    "status": "missing",
                    "evidence_ids": [],
                }
            ]
        },
    }


def _recovery_trace() -> list[dict]:
    return [
        {"stage": "planner", "reason": "doc"},
        {
            "stage": "evidence_rebind",
            "recovery_action": "rebind_existing_evidence",
            "slot_state_changed": False,
        },
        {
            "stage": "focused_retrieval",
            "new_evidence_ids": [],
            "semantic_slot_state_changed": False,
        },
        {
            "stage": "evidence_rebind",
            "recovery_action": "stop_without_reverify",
            "stop_reason": "recovery_no_progress",
        },
    ]


def test_qasper_semantic_debug_row_projects_the_full_consistency_chain() -> None:
    [row] = qasper_semantic_debug_rows([_prediction()])

    assert row["contract_id"] == "qasper_semantic_pipeline_debug.v2"
    assert row["example_id"] == "example-1"
    assert (
        row["semantic_verifier"]["debug_trace"]["events"][0]["auditor_relationship"]
        == "same_instance"
    )
    assert row["semantic_authority"]["reason"] == ("semantic_premise_fragment_invalid")
    assert [event["stage"] for event in row["recovery_events"]] == [
        "evidence_rebind",
        "focused_retrieval",
        "evidence_rebind",
    ]
    assert row["required_slot_states"] == [
        {
            "slot_id": "support:boolean_proposition",
            "status": "missing",
            "evidence_ids": [],
        }
    ]
    assert {finding["code"] for finding in row["findings"]} == {
        "audit_verified_authority_rejected",
        "same_instance_proposal_and_audit",
        "recovery_stopped_without_state_change",
    }


def test_qasper_semantic_debug_summary_counts_each_finding() -> None:
    rows = qasper_semantic_debug_rows([_prediction()])

    assert qasper_semantic_debug_summary(rows) == {
        "qasper_semantic_debug_trace_count": 1,
        "qasper_semantic_debug_finding_count": 3,
        "qasper_semantic_debug_findings": {
            "audit_verified_authority_rejected": 1,
            "recovery_stopped_without_state_change": 1,
            "same_instance_proposal_and_audit": 1,
        },
    }


def test_qasper_semantic_debug_rows_ignore_normal_predictions() -> None:
    prediction = _prediction()
    del prediction["engine_terminal_evidence_bundle"]["metadata"][
        "semantic_proposition_verifier"
    ]["debug_trace"]

    assert qasper_semantic_debug_rows([prediction]) == []


def test_qasper_semantic_debug_flags_only_accepted_wrong_positive_polarity() -> None:
    prediction = _prediction()
    event = prediction["engine_terminal_evidence_bundle"]["metadata"][
        "semantic_proposition_verifier"
    ]["debug_trace"]["events"][0]
    event["outcome"] = {
        "status": "parsed",
        "verdict": "yes",
        "audit_status": "verified",
    }

    [row] = qasper_semantic_debug_rows([prediction])

    assert "positive_verdict_against_negative_gold" in {
        finding["code"] for finding in row["findings"]
    }


def test_qasper_semantic_debug_flags_audit_and_recovery_state_inconsistency() -> None:
    prediction = _prediction()
    verifier = prediction["engine_terminal_evidence_bundle"]["metadata"][
        "semantic_proposition_verifier"
    ]
    verifier.pop("conclusion_audit")
    verifier["recovery_transitions"] = [{"to": "proof_repair"}]
    verifier["full_reaudit"] = False
    prediction["controller_trace"].append(
        {
            "stage": "reverify",
            "semantic_pack_digest_applicable": True,
            "semantic_pack_digest_changed": False,
        }
    )

    [row] = qasper_semantic_debug_rows([prediction])

    codes = {finding["code"] for finding in row["findings"]}
    assert "verified_audit_conclusion_contract_missing" in codes
    assert "proof_repair_without_full_reaudit" in codes
    assert "reverify_without_semantic_pack_change" in codes
