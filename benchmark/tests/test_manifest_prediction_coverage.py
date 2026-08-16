from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = PROJECT_ROOT / "scripts/slurm/validate_benchmark_predictions.py"


def _write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_predictions(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def _manifest() -> dict[str, Any]:
    return {
        "schema_version": 2,
        "dataset_name": "qasper_validation_test",
        "documents": [],
        "examples": [{"example_id": "one"}, {"example_id": "two"}],
        "routes": [{"route_id": "text"}, {"route_id": "controller"}],
    }


def _validate(predictions: Path, manifest: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            str(predictions),
            "--manifest",
            str(manifest),
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_validator_accepts_exact_cross_product_including_failure_row(
    tmp_path: Path,
) -> None:
    manifest = tmp_path / "manifest.json"
    predictions = tmp_path / "predictions.jsonl"
    _write_json(manifest, _manifest())
    _write_predictions(
        predictions,
        [
            {"example_id": "one", "route": "text", "error": None},
            {"example_id": "one", "route": "controller", "error": None},
            {"example_id": "two", "route": "text", "error": None},
            {
                "example_id": "two",
                "route": "controller",
                "error": "backend failed",
                "terminal_outcome": "execution_failed",
            },
        ],
    )

    result = _validate(predictions, manifest)

    assert result.returncode == 0, result.stderr
    assert "manifest_prediction_coverage=4/4" in result.stdout


def test_validator_rejects_missing_manifest_route_prediction(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    predictions = tmp_path / "predictions.jsonl"
    _write_json(manifest, _manifest())
    _write_predictions(
        predictions,
        [
            {"example_id": "one", "route": "text", "error": None},
            {"example_id": "one", "route": "controller", "error": None},
            {"example_id": "two", "route": "text", "error": None},
        ],
    )

    result = _validate(predictions, manifest)

    assert result.returncode != 0
    assert "manifest/prediction key mismatch" in result.stderr


def test_validator_rejects_duplicate_prediction_key(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    predictions = tmp_path / "predictions.jsonl"
    one = _manifest()
    one["examples"] = [{"example_id": "one"}]
    one["routes"] = [{"route_id": "text"}]
    _write_json(manifest, one)
    _write_predictions(
        predictions,
        [
            {"example_id": "one", "route": "text", "error": None},
            {"example_id": "one", "route": "text", "error": None},
        ],
    )

    result = _validate(predictions, manifest)

    assert result.returncode != 0
    assert "duplicate prediction key" in result.stderr


def test_validator_rejects_duplicate_manifest_identity(tmp_path: Path) -> None:
    manifest = tmp_path / "manifest.json"
    predictions = tmp_path / "predictions.jsonl"
    duplicate = _manifest()
    duplicate["examples"] = [
        {"example_id": "one"},
        {"example_id": "one"},
    ]
    duplicate["routes"] = [{"route_id": "text"}]
    _write_json(manifest, duplicate)
    _write_predictions(
        predictions,
        [{"example_id": "one", "route": "text", "error": None}],
    )

    result = _validate(predictions, manifest)

    assert result.returncode != 0
    assert "duplicate example_id" in result.stderr
