from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from ktem.docqa.terminal_semantic_commit import build_terminal_semantic_commit

from scripts.slurm.validate_contract_smoke import HARD_GATES, QASPER_HARD_GATES

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = PROJECT_ROOT / "scripts/slurm/validate_contract_smoke.py"
CORE_STAGES = (
    "canonical_candidate_evidence",
    "fused_evidence",
    "reranker_input_evidence",
    "selected_evidence",
    "generation_context_evidence",
    "verified_claim_support_evidence",
    "emitted_citation_evidence",
)
QASPER_REQUIREMENTS = (
    "ordinary_free_text",
    "yes_no",
    "support_and_contradiction",
    "cross_page_required_slots",
    "runtime_authority_pass_through",
)


def _evidence() -> dict[str, Any]:
    return {
        "canonical_id": "span:paper:s1",
        "source_id": "paper",
        "page_label": "1",
        "span_id": "s1",
        "evidence_level": "span",
        "text": "The paper reports the result.",
    }


def _prediction(requirements: list[str]) -> dict[str, Any]:
    item = _evidence()
    metadata: dict[str, Any] = {stage: [item] for stage in CORE_STAGES}
    metadata.update(
        {
            "ranking_trace": {"backend_execution": False},
            "query_plan": {
                "evidence_slots": [
                    {
                        "slot_id": "support:answer",
                        "role": "support",
                        "required": True,
                        "status": "filled",
                        "evidence_ids": ["span:paper:s1"],
                    }
                ]
            },
        }
    )
    return {
        "example_id": "smoke",
        "document_id": "paper",
        "document_ids": ["paper"],
        "question": "What result is reported?",
        "answer_type": "free_text",
        "gold_answers": ["The result."],
        "gold_evidence": [{"document_id": "paper", "page": 1}],
        "gold_source_ids": ["paper"],
        "gold_evidence_texts": ["The paper reports the result."],
        "source_identity_crosswalk": [
            {
                "canonical_dataset_id": "paper",
                "runtime_file_id": "paper-runtime",
                "runtime_source_id": "paper-runtime",
                "document_path": "/datasets/paper.pdf",
                "filename": "paper.pdf",
                "aliases": ["paper"],
            }
        ],
        "predicted_answer": "The result.",
        "answer_for_scoring": "The result.",
        "example_metadata": {
            "contract_smoke_requirements": requirements,
        },
        "evidence_metadata": metadata,
    }


def _write_run(
    run_dir: Path,
    *,
    predictions: list[dict[str, Any]],
    artifact_detail: str = "full",
) -> None:
    run_dir.mkdir()
    (run_dir / "summary.json").write_text(
        json.dumps({"artifact_detail": artifact_detail}),
        encoding="utf-8",
    )
    (run_dir / "predictions.jsonl").write_text(
        "".join(f"{json.dumps(row)}\n" for row in predictions),
        encoding="utf-8",
    )


def _attach_terminal_commit(prediction: dict[str, Any]) -> None:
    terminal_commit = build_terminal_semantic_commit(
        "yes",
        {
            "status": "supported",
            "action": "return",
            "canonical_answer_polarity": "yes",
        },
        {"status": "ok", "action": "return"},
        {
            "items": [_evidence()],
            "metadata": {"verified_claim_support_evidence": [_evidence()]},
        },
        presentation_answer="yes",
    ).as_dict()
    prediction["engine_terminal_state"]["terminal_semantic_commit"] = terminal_commit
    prediction["engine_terminal_commit"] = terminal_commit
    prediction["terminal_semantic_commit"] = terminal_commit


def test_contract_smoke_validator_accepts_full_auditable_artifact(tmp_path):
    run_dir = tmp_path / "run"
    requirements = list(QASPER_REQUIREMENTS)
    first = _prediction(requirements)
    first.update(
        {
            "question": "Did the paper report the result?",
            "answer_type": "boolean",
            "gold_answers": ["yes"],
            "predicted_answer": "yes",
            "answer_for_scoring": "yes",
            "engine_terminal_answer": "yes",
            "engine_terminal_state": {
                "contract_id": "engine_terminal_state.v1",
                "answer": "yes",
            },
            "engine_verify_decision": {"status": "supported"},
            "engine_terminal_projection_hash": "verified-projection",
            "contract_action": "pass_through",
            "contract_semantic_rewrite": False,
            "post_engine_answerability_llm_call_count": 0,
        }
    )
    _attach_terminal_commit(first)
    first["evidence_metadata"].update(
        {
            "qasper_answerability": {
                "status": "ok",
                "contract_action": "pass_through",
                "contract_semantic_rewrite": False,
                "engine_terminal_answer": "yes",
                "engine_semantic_label": "yes",
                "scored_semantic_label": "yes",
                "runtime_projection_present": True,
                "runtime_boolean_authority_applicable": True,
                "runtime_authority_failure_kind": "",
                "post_engine_answerability_llm_call_count": 0,
                "raw_verifier_verdict": "yes_complete",
                "final_post_contract_answer": "yes",
                "boolean_scope_valid": "true",
                "verifier_required_slot_ids": "support:boolean_proposition",
                "verifier_required_slot_count": "1",
                "verifier_required_slot_authority_count": "1",
                "verifier_required_evidence_ids": "span:paper:s1",
                "verifier_missing_required_slot_ids": "",
                "verifier_missing_required_evidence_ids": "",
                "verifier_required_authority_status": "complete",
                "verifier_required_evidence_coverage": "1.000000",
                "quote_ref_validation_status": "bound",
            },
        }
    )
    second = _prediction([])
    second["example_id"] = "smoke-2"
    _write_run(run_dir, predictions=[first, second])

    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            str(run_dir),
            "--suite-kind",
            "qasper",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "contract_smoke_status=passed" in result.stdout
    audit = json.loads((run_dir / "contract_smoke_audit.json").read_text())
    assert audit["artifact_detail"] == "full"
    assert audit["hard_gates"]["identity_collision_count"]["passed"] is True
    assert audit["stage_audits"][0]["reranked_evidence"]["status"] == (
        "truthfully_not_executed"
    )


def test_contract_smoke_validator_rejects_compact_or_incomplete_artifact(tmp_path):
    run_dir = tmp_path / "run"
    prediction = _prediction(["ordinary_free_text"])
    prediction["evidence_metadata"].pop("selected_evidence")
    second = _prediction([])
    second["example_id"] = "smoke-2"
    _write_run(
        run_dir,
        predictions=[prediction, second],
        artifact_detail="compact",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            str(run_dir),
            "--suite-kind",
            "qasper",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "artifact_detail must be full" in result.stderr


def test_contract_smoke_validator_rejects_missing_required_case(tmp_path):
    run_dir = tmp_path / "run"
    first = _prediction(["ordinary_free_text"])
    second = _prediction([])
    second["example_id"] = "smoke-2"
    _write_run(run_dir, predictions=[first, second])

    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            str(run_dir),
            "--suite-kind",
            "qasper",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "missing contract smoke requirements" in result.stderr


def test_qasper_contract_smoke_requires_runtime_authority_pass_through(tmp_path):
    run_dir = tmp_path / "run"
    requirements = list(QASPER_REQUIREMENTS)
    first = _prediction(requirements)
    second = _prediction([])
    second["example_id"] = "smoke-2"
    _write_run(run_dir, predictions=[first, second])

    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            str(run_dir),
            "--suite-kind",
            "qasper",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "runtime_authority_pass_through_not_observed" in result.stderr


def test_qasper_contract_smoke_declares_runtime_authority_hard_gates():
    assert {
        "abstention_candidate_sent_as_semantic_answer_count",
        "verifier_required_evidence_coverage",
        "qasper_required_slot_empty_state_count",
        "qasper_required_evidence_coverage_missing_count",
        "answerable_false_abstention_count",
        "boolean_scope_violation_count",
        "wrong_polarity_count",
        "citation_claim_support_violation_count",
        "citation_scope_violation_count",
        "contract_semantic_rewrite_count",
        "engine_scored_semantic_label_mismatch_count",
        "qasper_post_engine_answerability_llm_call_count",
        "qasper_runtime_authority_missing_count",
        "qasper_runtime_semantic_verifier_failure_count",
        "qasper_runtime_scope_failure_count",
        "qasper_quote_validation_ref_mismatch_count",
        "qasper_terminal_state_missing_count",
        "qasper_invalid_typed_label_count",
    } <= set(QASPER_HARD_GATES)
    assert "terminal_outcome_contract_violation_count" in HARD_GATES
