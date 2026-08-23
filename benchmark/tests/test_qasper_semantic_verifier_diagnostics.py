from __future__ import annotations

from benchmark.contract_invariant_metrics import contract_invariant_summary
from benchmark.qasper_contract_invariants import qasper_contract_metric_values
from benchmark.qasper_semantic_verifier_metrics import semantic_verifier_failure_metrics
from benchmark.reports import write_reports


def test_semantic_provider_rejection_reason_round_trips_through_metrics() -> None:
    cases = {
        "provider_context_length_exceeded": (1.0, 0.0),
        "provider_response_schema_unsupported": (0.0, 1.0),
    }
    for reason, expected in cases.items():
        prediction = {
            "answer_type": "boolean",
            "predicted_answer": "unanswerable",
            "gold_answers": ["yes"],
        }
        metadata = {
            "qasper_answerability": {
                "runtime_semantic_proposition_verifier_status": "failed",
                "runtime_semantic_proposition_verifier_reason": reason,
            }
        }

        metrics = qasper_contract_metric_values(
            prediction,
            metadata,
            cited=[],
            contract_items=[],
        )

        assert (
            metrics["qasper_semantic_proposition_verifier_context_overflow_count"],
            metrics["qasper_semantic_proposition_verifier_schema_unsupported_count"],
        ) == expected


def test_parse_and_entailment_audit_outcomes_have_distinct_metrics() -> None:
    cases = [
        (
            {
                "runtime_semantic_proposition_verifier_status": "failed",
                "runtime_semantic_proposition_verifier_reason": (
                    "provider_output_truncated"
                ),
                "runtime_semantic_proposition_verifier_parse_failure_reason": (
                    "json_decode_error"
                ),
                "runtime_semantic_entailment_audit_status": "not_started",
            },
            (1.0, 0.0, 0.0, 0.0, 0.0),
        ),
        (
            {
                "runtime_semantic_proposition_verifier_status": "failed",
                "runtime_semantic_proposition_verifier_reason": "invalid_model_json",
                "runtime_semantic_proposition_verifier_parse_failure_reason": (
                    "json_decode_error"
                ),
                "runtime_semantic_entailment_audit_status": "not_started",
            },
            (0.0, 1.0, 0.0, 0.0, 0.0),
        ),
        (
            {
                "runtime_semantic_proposition_verifier_status": "failed",
                "runtime_semantic_proposition_verifier_reason": "invalid_model_json",
                "runtime_semantic_proposition_verifier_parse_failure_reason": (
                    "premise_slot_binding_invalid"
                ),
                "runtime_semantic_entailment_audit_status": "not_started",
            },
            (0.0, 0.0, 1.0, 0.0, 0.0),
        ),
        (
            {
                "runtime_semantic_proposition_verifier_status": "audit_rejected",
                "runtime_semantic_proposition_verifier_reason": (
                    "semantic_entailment_audit_rejected"
                ),
                "runtime_semantic_entailment_audit_status": "rejected",
            },
            (0.0, 0.0, 0.0, 0.0, 1.0),
        ),
        (
            {
                "runtime_semantic_proposition_verifier_status": "failed",
                "runtime_semantic_proposition_verifier_reason": (
                    "invalid_entailment_audit_json"
                ),
                "runtime_semantic_entailment_audit_status": "failed",
            },
            (0.0, 0.0, 0.0, 1.0, 0.0),
        ),
    ]
    for trace, expected in cases:
        prediction = {
            "answer_type": "boolean",
            "predicted_answer": "unanswerable",
            "gold_answers": ["yes"],
        }
        metrics = qasper_contract_metric_values(
            prediction,
            {"qasper_answerability": trace},
            cited=[],
            contract_items=[],
        )

        assert (
            metrics["qasper_semantic_proposition_output_truncation_count"],
            metrics["qasper_semantic_proposition_json_decode_failure_count"],
            metrics["qasper_semantic_proposition_parse_contract_rejection_count"],
            metrics["qasper_semantic_entailment_audit_failure_count"],
            metrics["qasper_semantic_entailment_audit_rejection_count"],
        ) == expected


def test_final_row_audit_rejection_is_distinct_from_raw_audit_call_rejection() -> None:
    raw_rejection = {
        "runtime_semantic_proposition_verifier_status": "audit_rejected",
        "runtime_semantic_entailment_audit_status": "rejected",
        "runtime_semantic_proposition_verifier_reason": (
            "semantic_entailment_audit_rejected"
        ),
    }
    raw_metrics = semantic_verifier_failure_metrics(raw_rejection)

    assert raw_metrics["qasper_semantic_entailment_audit_rejection_count"] == 1.0
    assert (
        raw_metrics["qasper_semantic_proposition_verifier_audit_rejection_count"] == 1.0
    )
    assert (
        raw_metrics["qasper_semantic_audit_verified_but_runtime_rejected_count"] == 0.0
    )

    reused_rejection = {
        **raw_rejection,
        "runtime_semantic_proposition_verifier_status": "parsed",
    }
    reused_metrics = semantic_verifier_failure_metrics(reused_rejection)

    assert reused_metrics["qasper_semantic_entailment_audit_rejection_count"] == 1.0
    assert (
        reused_metrics["qasper_semantic_proposition_verifier_audit_rejection_count"]
        == 0.0
    )

    runtime_rejection = {
        "runtime_semantic_proposition_verifier_status": "parsed",
        "runtime_semantic_proposition_authority_status": "rejected",
        "runtime_semantic_entailment_audit_status": "verified",
    }
    runtime_metrics = semantic_verifier_failure_metrics(runtime_rejection)

    assert runtime_metrics["qasper_semantic_entailment_audit_rejection_count"] == 0.0
    assert (
        runtime_metrics["qasper_semantic_proposition_verifier_audit_rejection_count"]
        == 0.0
    )
    assert (
        runtime_metrics["qasper_semantic_audit_verified_but_runtime_rejected_count"]
        == 1.0
    )


def test_repaired_row_preserves_raw_audit_call_and_runtime_rejection_counts() -> None:
    metrics = semantic_verifier_failure_metrics(
        {
            "runtime_semantic_proposition_verifier_status": "parsed",
            "runtime_semantic_entailment_audit_status": "verified",
            "runtime_semantic_entailment_audit_rejection_count": 2,
            "runtime_semantic_audit_verified_but_runtime_rejected_count": 1,
            "runtime_semantic_proposition_authority_status": "verified",
        }
    )

    assert metrics["qasper_semantic_entailment_audit_rejection_count"] == 2.0
    assert metrics["qasper_semantic_proposition_verifier_audit_rejection_count"] == 0.0
    assert metrics["qasper_semantic_audit_verified_but_runtime_rejected_count"] == 1.0


def test_audit_verified_runtime_rejection_unique_examples_are_deduplicated() -> None:
    trace = {
        "runtime_semantic_proposition_verifier_status": "parsed",
        "runtime_semantic_proposition_authority_status": "rejected",
        "runtime_semantic_entailment_audit_status": "verified",
    }
    predictions = [
        {
            "example_id": "qasper-example",
            "route": route,
            "answer_type": "boolean",
            "predicted_answer": "unanswerable",
            "gold_answers": ["yes"],
            "evidence_metadata": {"qasper_answerability": dict(trace)},
        }
        for route in ("text_rag", "hybrid_rag")
    ]

    summary = contract_invariant_summary(predictions)

    assert summary["qasper_semantic_audit_verified_but_runtime_rejected_count"] == 2.0
    assert (
        summary[
            "qasper_semantic_audit_verified_but_runtime_rejected_unique_example_count"
        ]
        == 1
    )


def test_write_reports_surfaces_qasper_semantic_verifier_failures(tmp_path) -> None:
    report = {
        "summary": {
            "suite_name": "QASPER focused",
            "dataset_name": "qasper_typed_v2",
            "num_examples": 1,
            "num_documents": 1,
            "qasper_composite_authority_count": 0.0,
            "qasper_composite_authority_invalid_count": 0.0,
            "qasper_semantic_evidence_set_authority_count": 0.0,
            "qasper_semantic_evidence_set_authority_invalid_count": 1.0,
            "qasper_semantic_proposition_verifier_call_count": 2.0,
            "qasper_semantic_proposition_verifier_failure_count": 1.0,
            "qasper_semantic_proposition_verifier_context_overflow_count": 1.0,
            "qasper_semantic_proposition_verifier_schema_unsupported_count": 0.0,
            "qasper_semantic_proposition_output_truncation_count": 0.0,
            "qasper_semantic_proposition_json_decode_failure_count": 0.0,
            "qasper_semantic_proposition_parse_contract_rejection_count": 0.0,
            "qasper_semantic_entailment_audit_call_count": 0.0,
            "qasper_semantic_entailment_audit_failure_count": 0.0,
            "qasper_semantic_entailment_audit_rejection_count": 0.0,
            "qasper_required_slot_authority_missing_count": 1.0,
        },
        "predictions": [{"example_id": "qasper-1"}],
        "documents": [{"document_id": "paper-1"}],
    }

    run_dir = write_reports(report, tmp_path, "QASPER focused")
    markdown = (run_dir / "report.md").read_text(encoding="utf-8")

    assert "## QASPER Authority Diagnostics" in markdown
    assert "qasper_semantic_proposition_verifier_failure_count | 1.0" in markdown
    assert (
        "qasper_semantic_proposition_verifier_context_overflow_count | 1.0" in markdown
    )
    assert "qasper_required_slot_authority_missing_count | 1.0" in markdown
