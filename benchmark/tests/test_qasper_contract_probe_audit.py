from __future__ import annotations

import json

import pytest

from benchmark.tests.qasper_debug_contract_fixtures import _qasper_debug_prediction
from scripts.slurm.validate_qasper_contract_probe import validate_contract_probe


def _probe_rows() -> list[dict]:
    rows = [
        _qasper_debug_prediction(f"example-{index}", route)
        for index in range(1, 7)
        for route in ("controller_auto", "crag_guarded", "hybrid_rag")
    ]
    for row in rows:
        row["qasper_debug_lane"] = "contract_probe"
    return rows


def _write_rows(path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_provider_contract_probe_audit_passes_required_live_states(tmp_path) -> None:
    predictions = tmp_path / "contract_probe_predictions.jsonl"
    output = tmp_path / "contract_probe_audit.json"
    _write_rows(predictions, _probe_rows())

    audit = validate_contract_probe(predictions, output_path=output)

    assert audit["status"] == "passed"
    assert audit["contract_probe_audit"]["live_state_matrix_complete"] is False
    assert not audit["failed_gates"]
    assert json.loads(output.read_text())["status"] == "passed"


def test_provider_contract_probe_audit_fails_before_quality_run(tmp_path) -> None:
    rows = _probe_rows()[:3]
    predictions = tmp_path / "contract_probe_predictions.jsonl"
    output = tmp_path / "contract_probe_audit.json"
    _write_rows(predictions, rows)

    with pytest.raises(ValueError, match="provider contract probe failed"):
        validate_contract_probe(predictions, output_path=output)

    audit = json.loads(output.read_text())
    assert audit["status"] == "failed"
    assert (
        "qasper_contract_probe_required_online_states_complete" in audit["failed_gates"]
    )
