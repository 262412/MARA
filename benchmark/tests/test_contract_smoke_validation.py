from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from benchmark.tests.contract_smoke_fixtures import (
    _attach_terminal_commit,
    _prediction,
    _write_run,
)
from scripts.slurm.validate_contract_smoke import QASPER_HARD_GATES

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = PROJECT_ROOT / "scripts/slurm/validate_contract_smoke.py"
QASPER_REQUIREMENTS = (
    "ordinary_free_text",
    "yes_no",
    "support_and_contradiction",
    "cross_page_required_slots",
    "runtime_authority_pass_through",
)


def _annotation_diagnostics(
    *,
    ambiguous: bool,
    reason: str = "",
) -> dict[str, object]:
    return {
        "contract_id": "qasper_annotation_diagnostics.v1",
        "ambiguous": ambiguous,
        "ambiguity_reasons": [reason] if reason else [],
    }


def _complete_qasper_answerability() -> dict[str, object]:
    return {
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
    }


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
            "qasper_annotation_diagnostics": _annotation_diagnostics(ambiguous=False),
        }
    )
    _attach_terminal_commit(first)
    first["evidence_metadata"].update(
        {
            "qasper_answerability": _complete_qasper_answerability(),
        }
    )
    second = _prediction([])
    second["example_id"] = "smoke-2"
    second["qasper_annotation_diagnostics"] = _annotation_diagnostics(
        ambiguous=True,
        reason="fixture_expected_ambiguity",
    )
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
    audit = json.loads((run_dir / "contract_smoke_audit.json").read_text())
    assert audit["status"] == "failed"
    assert (
        "artifact_detail must be full for contract smoke"
        in audit["precondition_violations"]
    )


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
        "qasper_composite_authority_invalid_count",
        "qasper_semantic_evidence_set_authority_invalid_count",
        "qasper_semantic_proposition_verifier_failure_count",
        "qasper_quote_validation_ref_mismatch_count",
        "qasper_terminal_state_missing_count",
        "qasper_invalid_typed_label_count",
        "qasper_canonical_semantic_pack_mismatch_count",
    } <= set(QASPER_HARD_GATES)
