from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = PROJECT_ROOT / "scripts/slurm/validate_benchmark_predictions.py"


def _write_predictions(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(f"{json.dumps(row)}\n" for row in rows),
        encoding="utf-8",
    )


def test_validator_accepts_artifact_with_usable_prediction(tmp_path):
    predictions = tmp_path / "predictions.jsonl"
    _write_predictions(
        predictions,
        [
            {"example_id": "failed", "error": "connection refused"},
            {"example_id": "usable", "answer": "yes", "error": None},
        ],
    )

    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(predictions)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "usable_predictions=1" in result.stdout


def test_validator_rejects_artifact_when_every_prediction_failed(tmp_path):
    predictions = tmp_path / "predictions.jsonl"
    _write_predictions(
        predictions,
        [
            {"example_id": "first", "error": "connection refused"},
            {"example_id": "second", "error": "backend unavailable"},
        ],
    )

    result = subprocess.run(
        [sys.executable, str(VALIDATOR), str(predictions)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "zero usable predictions" in result.stderr


def test_validator_rejects_partial_formal_artifact_when_all_usable_is_required(
    tmp_path,
):
    predictions = tmp_path / "predictions.jsonl"
    _write_predictions(
        predictions,
        [
            {"example_id": "usable", "answer": "yes", "error": None},
            {"example_id": "failed", "error": "maximum context length exceeded"},
        ],
    )

    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            str(predictions),
            "--require-all-usable",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "requires every prediction to be usable" in result.stderr


def test_validator_rejects_unexpected_prediction_count(tmp_path):
    predictions = tmp_path / "predictions.jsonl"
    _write_predictions(
        predictions,
        [{"example_id": "usable", "answer": "yes", "error": None}],
    )

    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            str(predictions),
            "--expected-count",
            "2",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "expected 2 predictions but found 1" in result.stderr


def test_validator_rejects_unavailable_required_hybrid_route(tmp_path):
    predictions = tmp_path / "predictions.jsonl"
    _write_predictions(
        predictions,
        [
            {
                "example_id": "numeric",
                "error": None,
                "controller_decision": {
                    "required_evidence_route_available": False,
                },
            }
        ],
    )

    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            str(predictions),
            "--require-hybrid-eligible",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "required hybrid evidence was unavailable" in result.stderr


def test_validator_accepts_available_required_hybrid_route(tmp_path):
    predictions = tmp_path / "predictions.jsonl"
    _write_predictions(
        predictions,
        [
            {
                "example_id": "numeric",
                "error": None,
                "controller_decision": {
                    "required_evidence_route_available": True,
                },
            },
            {
                "example_id": "simple",
                "error": None,
                "controller_decision": {
                    "required_evidence_route_available": None,
                },
            },
        ],
    )

    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            str(predictions),
            "--require-hybrid-eligible",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "required_hybrid_eligible=1/1" in result.stdout


def test_validator_rejects_qasper_boolean_without_answerability_trace(tmp_path):
    predictions = tmp_path / "predictions.jsonl"
    _write_predictions(
        predictions,
        [
            {
                "example_id": "boolean",
                "answer_type": "boolean",
                "predicted_answer": "yes",
                "error": None,
                "evidence_metadata": {},
            }
        ],
    )

    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            str(predictions),
            "--require-qasper-answerability",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "QASPER answerability trace was missing" in result.stderr


def test_validator_accepts_qasper_boolean_with_answerability_trace(tmp_path):
    predictions = tmp_path / "predictions.jsonl"
    _write_predictions(
        predictions,
        [
            {
                "example_id": "boolean",
                "answer_type": "boolean",
                "predicted_answer": "yes",
                "error": None,
                "evidence_metadata": {
                    "qasper_answerability": {
                        "contract_id": "qasper_answerability.v10",
                        "status": "ok",
                    }
                },
            }
        ],
    )

    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            str(predictions),
            "--require-qasper-answerability",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "qasper_answerability_coverage=1/1" in result.stdout
