from __future__ import annotations

import json

import pytest

from benchmark.artifact_publication import (
    publish_artifact_contract,
    publish_contract_smoke_audit,
)
from benchmark.jsonl import read_jsonl
from benchmark.qasper_semantic_debug_artifact import qasper_semantic_debug_rows
from benchmark.reports import write_reports
from scripts.slurm.validate_contract_smoke import validate


def _pre_verifier_prediction() -> dict:
    generation = {
        "contract_id": "qasper_typed_candidate_generation.v2",
        "status": "failed",
        "failure_reason": "provider_context_length_exceeded",
        "provider_failure_reason": "provider_context_length_exceeded",
        "provider_failure_detail": "request exceeded provider context window",
        "message_stack": [
            {"index": 0, "role": "system", "content": "candidate"},
            {"index": 1, "role": "user", "content": "question"},
        ],
        "raw_response": "",
        "cleaned_response": "",
        "raw_candidate": "",
        "typed_candidate": "",
        "finish_reason": "",
        "input_digest": "generator-input",
        "output_digest": "",
        "transaction_id": "generator:pre-verifier",
        "attempt_id": "generator:pre-verifier:1",
        "effective_seed": 20260724,
        "attempts": [
            {
                "attempt_id": "generator:pre-verifier:1",
                "status": "provider_failed",
                "failure_reason": "provider_context_length_exceeded",
                "failure_detail": "request exceeded provider context window",
            }
        ],
    }
    return {
        "example_id": "pre-verifier",
        "route": "hybrid_rag",
        "question": "Did the authors use the method?",
        "gold_answers": ["yes"],
        "predicted_answer": "",
        "answer_status": "failed",
        "terminal_outcome": "execution_failed",
        "terminal_outcome_reason": "candidate generation failed",
        "evidence_metadata": {"qasper_candidate_generation": generation},
    }


def test_pre_verifier_failure_is_projected_with_complete_failure_context() -> None:
    [row] = qasper_semantic_debug_rows([_pre_verifier_prediction()])

    assert row["example_id"] == "pre-verifier"
    assert row["provider_failure_reason"] == "provider_context_length_exceeded"
    assert row["provider_failure_detail"] == "request exceeded provider context window"
    assert row["raw_response"] == ""
    assert row["cleaned_response"] == ""
    assert row["typed_candidate"] == ""
    assert row["verifier_status"] == "not_started"
    assert row["auditor_status"] == "not_started"
    assert row["semantic_verifier"]["candidate_verification_status"] == (
        "pre_audit_failed"
    )
    assert row["semantic_verifier"]["candidate_verification_audit"] == {
        "contract_id": "candidate_verifier_audit.v2",
        "status": "not_started",
        "mode": "not_started",
        "audited_candidate": "",
        "audited_judgment": "pre_audit_failed",
        "classification": "pre_audit_failed",
        "replacement_candidate_allowed": False,
        "reason": "provider_context_length_exceeded",
    }
    assert row["transaction_identity"] == {
        "contract_id": "qasper_cross_route_transaction_trace.v1",
        "trace_group_id": "",
        "generator_transaction_id": "generator:pre-verifier",
        "generator_attempt_id": "generator:pre-verifier:1",
        "verifier_transaction_id": "",
        "verifier_attempt_id": "",
        "auditor_attempt_id": "",
        "generator_effective_seed": 20260724,
        "verifier_effective_seed": None,
        "generator_input_digest": "generator-input",
        "generator_output_digest": "",
        "verifier_input_digest": "",
        "verifier_output_digest": "",
    }
    assert row["message_stack"] == row["main_candidate_generator"]["message_stack"]
    assert row["finish_reason"] == ""


def test_pre_verifier_failure_is_not_classified_as_false_abstention() -> None:
    prediction = _pre_verifier_prediction()
    prediction["predicted_answer"] = "unanswerable"

    [row] = qasper_semantic_debug_rows([prediction])

    analysis = row["candidate_authority_analysis"]
    assert analysis["false_abstention_cause"] == ""
    assert analysis["execution_failure_before_verification"] is True


def test_candidate_parse_failure_is_not_reported_as_provider_failure() -> None:
    prediction = _pre_verifier_prediction()
    generation = prediction["evidence_metadata"]["qasper_candidate_generation"]
    generation.pop("provider_failure_reason")
    generation.pop("provider_failure_detail")
    generation["raw_response"] = "not-json"
    generation["cleaned_response"] = "not-json"
    generation["failure_reason"] = "json_decode_error"
    generation["raw_candidate_failure_reason"] = "json_decode_error"
    generation["attempts"] = [
        {
            "attempt_id": "generator:pre-verifier:1",
            "status": "failed",
            "failure_reason": "json_decode_error",
        }
    ]

    [row] = qasper_semantic_debug_rows([prediction])

    assert row["provider_failure_reason"] == ""
    assert row["provider_failure_detail"] == ""
    assert row["parse_failure_reason"] == "json_decode_error"
    assert row["execution_failure_kind"] == "candidate_parse_failure"


def test_required_artifact_is_marked_incomplete_when_semantic_trace_is_absent(
    tmp_path,
) -> None:
    run_dir = tmp_path / "missing-semantic"
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(
        json.dumps({"artifact_detail": "full"}), encoding="utf-8"
    )
    (run_dir / "predictions.jsonl").write_text("{}\n", encoding="utf-8")

    marker = publish_artifact_contract(
        run_dir,
        run_requirements={"semantic_debug_traces": True},
    )

    assert marker["complete"] is False
    assert "semantic_debug_traces.jsonl" in marker["missing_required_files"]
    manifest = json.loads((run_dir / "artifact_manifest.json").read_text())
    assert "semantic_debug_traces.jsonl" in manifest["required_files"]


def test_required_semantic_trace_is_incomplete_when_prediction_row_is_missing(
    tmp_path,
) -> None:
    run_dir = tmp_path / "empty-semantic"
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(
        json.dumps({"artifact_detail": "full", "num_predictions": 1}),
        encoding="utf-8",
    )
    (run_dir / "predictions.jsonl").write_text("{}\n", encoding="utf-8")
    (run_dir / "semantic_debug_traces.jsonl").write_text("", encoding="utf-8")

    marker = publish_artifact_contract(
        run_dir,
        run_requirements={"semantic_debug_traces": True},
    )

    assert marker["complete"] is False
    assert "semantic_debug_traces.jsonl" in marker["missing_required_files"]


def test_contract_smoke_publishes_failed_audit_for_required_semantic_trace_gap(
    tmp_path,
) -> None:
    run_dir = tmp_path / "smoke-missing-semantic"
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(
        json.dumps({"artifact_detail": "full"}), encoding="utf-8"
    )
    (run_dir / "predictions.jsonl").write_text(
        json.dumps({"example_id": "one"}) + "\n", encoding="utf-8"
    )
    (run_dir / "artifact_manifest.json").write_text(
        json.dumps({"run_requirements": ["semantic_debug_traces.jsonl"]}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="semantic_debug_trace"):
        validate(run_dir, suite_kind="qasper_debug")

    audit = json.loads(
        (run_dir / "contract_smoke_audit.json").read_text(encoding="utf-8")
    )
    assert audit["status"] == "failed"
    assert audit["failed_gates"] == ["preconditions"]
    assert any(
        violation.startswith("semantic_debug_trace")
        for violation in audit["precondition_violations"]
    )


def test_failed_contract_audit_is_atomically_published_and_completes_requirements(
    tmp_path,
) -> None:
    report = {
        "summary": {
            "suite_name": "QASPER failure artifact",
            "dataset_name": "qasper",
            "num_examples": 1,
            "num_documents": 0,
        },
        "predictions": [_pre_verifier_prediction()],
        "documents": [],
        "run_requirements": {
            "semantic_debug_traces": True,
            "contract_smoke_audit": True,
        },
    }

    run_dir = write_reports(report, tmp_path, "QASPER failure artifact")
    marker_before = json.loads(
        (run_dir / "artifact_complete.json").read_text(encoding="utf-8")
    )
    assert marker_before["complete"] is False
    assert not (run_dir / "contract_smoke_audit.json").exists()
    assert len(read_jsonl(run_dir / "semantic_debug_traces.jsonl")) == 1

    publish_contract_smoke_audit(
        run_dir,
        {
            "contract": "contract_smoke_audit.v2",
            "status": "failed",
            "failed_gates": ["qasper_debug_observability"],
        },
    )

    assert json.loads((run_dir / "contract_smoke_audit.json").read_text())[
        "status"
    ] == ("failed")
    marker_after = json.loads(
        (run_dir / "artifact_complete.json").read_text(encoding="utf-8")
    )
    assert marker_after["complete"] is True


@pytest.mark.parametrize(
    "requirement", ("semantic_debug_traces", "contract_smoke_audit")
)
def test_run_requirements_are_preserved_across_republication(tmp_path, requirement):
    run_dir = tmp_path / requirement
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(
        json.dumps({"artifact_detail": "full"}), encoding="utf-8"
    )
    (run_dir / "predictions.jsonl").write_text("{}\n", encoding="utf-8")
    publish_artifact_contract(run_dir, run_requirements={requirement: True})

    if requirement == "semantic_debug_traces":
        (run_dir / "semantic_debug_traces.jsonl").write_text("{}\n", encoding="utf-8")
    else:
        (run_dir / "contract_smoke_audit.json").write_text(
            json.dumps({"status": "failed"}), encoding="utf-8"
        )
    marker = publish_artifact_contract(run_dir)

    assert marker["complete"] is True
