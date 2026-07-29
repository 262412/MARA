from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

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


def test_contract_smoke_validator_accepts_full_auditable_artifact(tmp_path):
    run_dir = tmp_path / "run"
    requirements = [
        "ordinary_free_text",
        "yes_no",
        "support_and_contradiction",
        "cross_page_required_slots",
        "answerability_rewrite",
    ]
    first = _prediction(requirements)
    first.update(
        {
            "gold_answers": ["unanswerable"],
            "predicted_answer": "unanswerable",
            "answer_for_scoring": "unanswerable",
            "pre_contract_verification": {
                "answer": "yes",
                "verify_decision": {"status": "supported"},
            },
            "post_contract_verification": {
                "answer": "unanswerable",
                "verify_decision": {"status": "not_enough_evidence"},
            },
            "verify_decision": {"status": "not_enough_evidence"},
        }
    )
    first["evidence_metadata"].update(
        {
            "verify_decision": {"status": "not_enough_evidence"},
            "answer_dependent_state": "post_contract_verified",
            "qasper_answerability": {
                "action": "abstained_insufficient_evidence",
                "primary_answer": "yes",
                "citation_state": "cleared_for_rebind",
                "status": "ok",
                "verifier_input_evidence_ids": "span:paper:s1",
                "verifier_dropped_evidence_ids": "",
                "verifier_input_character_count": "29",
                "verifier_input_token_count": "5",
                "verifier_budget_exhausted": "false",
                "candidate_for_answerability": "yes",
                "verifier_required_evidence_ids": "span:paper:s1",
                "verifier_required_evidence_coverage": "1.000000",
            },
            "answerability_contract_trace": {
                "pre_contract_answer": "yes",
                "post_contract_answer": "unanswerable",
                "rewrite_applied": True,
                "rewrite_type": "polarity_to_unanswerable",
                "rewrite_reason": "insufficient_evidence",
                "pre_contract_verification": {},
                "post_contract_verification": {},
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


def test_qasper_contract_smoke_requires_an_observed_answer_rewrite(tmp_path):
    run_dir = tmp_path / "run"
    requirements = [
        "ordinary_free_text",
        "yes_no",
        "support_and_contradiction",
        "cross_page_required_slots",
        "answerability_rewrite",
    ]
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
    assert "answerability_rewrite_not_observed" in result.stderr
