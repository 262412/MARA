from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from benchmark.tests.qasper_debug_contract_fixtures import _qasper_debug_prediction
from scripts.slurm import qasper_debug_contract_probe as probe
from scripts.slurm import validate_qasper_contract_probe as probe_validator


def _probe_row(case: probe.ProbeCase, index: int) -> dict:
    states = {
        "supported_yes": ("supported", "passed", False),
        # This is deliberately wrong for the case: the live row observes yes
        # where the probe contract expects no.  The rows are otherwise complete
        # production-shaped evidence so the failure is a coverage failure.
        "supported_no": ("supported", "passed", False),
        "contradicted_yes": ("contradicted", "passed", False),
        "contradicted_no": ("contradicted", "passed", False),
        "unknown_audited": ("unknown", "passed", False),
        "auditor_fail": ("unknown", "failed", False),
    }
    candidates = {
        "supported_yes": "yes",
        "supported_no": "yes",
        "contradicted_yes": "yes",
        "contradicted_no": "no",
        "unknown_audited": "yes",
        "auditor_fail": "yes",
    }
    row = _qasper_debug_prediction(
        f"probe-{index + 1}",
        "contract_probe",
        state=states[case.case_id],
        candidate=candidates[case.case_id],
    )
    row["contract_id"] = probe._MODEL_CONTRACT
    row["quality_lane_excluded"] = True
    row["example_metadata"]["contract_probe_case"] = {"case_id": case.case_id}
    row["qasper_debug_lane"] = "contract_probe"
    return row


def test_probe_persists_rows_and_failed_audit_on_coverage_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    predictions = tmp_path / "contract_probe_predictions.jsonl"
    audit = tmp_path / "contract_probe_audit.json"
    monkeypatch.setattr(
        probe,
        "_run_case",
        lambda case, index, **_: _probe_row(case, index),
    )
    original_hard_gate = probe._assert_live_coverage

    def _assert_artifacts_precede_hard_gate(rows: list[dict]) -> None:
        assert len(predictions.read_text(encoding="utf-8").splitlines()) == len(rows)
        pending = json.loads(audit.read_text(encoding="utf-8"))
        assert pending["status"] == "failed"
        assert pending["failure_evidence"]["probe_execution"] == {
            "phase": "pre_hard_gate",
            "hard_gate_complete": False,
        }
        original_hard_gate(rows)

    monkeypatch.setattr(
        probe,
        "_assert_live_coverage",
        _assert_artifacts_precede_hard_gate,
    )
    monkeypatch.setattr(
        probe_validator,
        "_assert_live_coverage",
        _assert_artifacts_precede_hard_gate,
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "qasper_debug_contract_probe",
            "--base-url",
            "http://provider.invalid/v1",
            "--model",
            "contract-probe-model",
            "--auditor-base-url",
            "http://auditor.invalid/v1",
            "--auditor-model",
            "heterogeneous-auditor-model",
            "--output",
            str(predictions),
            "--audit-output",
            str(audit),
        ],
    )

    with pytest.raises(Exception):
        probe.main()

    rows = predictions.read_text(encoding="utf-8").splitlines()
    assert len(rows) == len(probe._PROBE_CASES)
    assert not list(tmp_path.glob(f".{predictions.name}.*.tmp"))

    payload = json.loads(audit.read_text(encoding="utf-8"))
    assert payload["contract"] == "qasper_provider_contract_probe_audit.v1"
    assert payload["status"] == "failed"
    assert payload["source_sha256"]
    assert payload["replacement_candidate_allowed"] is False
    assert payload["failed_gates"]
    assert payload["contract_probe_audit"]["status"] == "failed"
    assert payload["contract_probe_audit"]["failed_gates"] == payload["failed_gates"]
    assert (
        payload["contract_probe_audit"]["failure_evidence"]
        == payload["failure_evidence"]
    )
    assert payload["failure_evidence"]["observed_state"]["prediction_count"] == len(
        probe._PROBE_CASES
    )
    assert any(
        row["case_id"] == "supported_no" and row["candidate"] == "yes"
        for row in payload["failure_evidence"]["observed_state"]["rows"]
    )


def test_probe_persists_partial_rows_and_exception_audit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    predictions = tmp_path / "contract_probe_predictions.jsonl"
    audit = tmp_path / "contract_probe_audit.json"

    def _run_case(case: probe.ProbeCase, index: int, **_: object) -> dict:
        if index == 2:
            raise RuntimeError("provider timeout while generating auditor proof")
        return _probe_row(case, index)

    monkeypatch.setattr(probe, "_run_case", _run_case)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "qasper_debug_contract_probe",
            "--base-url",
            "http://provider.invalid/v1",
            "--model",
            "contract-probe-model",
            "--auditor-base-url",
            "http://auditor.invalid/v1",
            "--auditor-model",
            "heterogeneous-auditor-model",
            "--output",
            str(predictions),
            "--audit-output",
            str(audit),
        ],
    )

    with pytest.raises(RuntimeError, match="provider timeout"):
        probe.main()

    assert len(predictions.read_text(encoding="utf-8").splitlines()) == 2
    payload = json.loads(audit.read_text(encoding="utf-8"))
    assert payload["contract"] == "qasper_provider_contract_probe_audit.v1"
    assert payload["status"] == "failed"
    assert payload["source_sha256"]
    assert payload["replacement_candidate_allowed"] is False
    assert payload["failed_gates"]
    assert payload["contract_probe_audit"]["status"] == "failed"
    assert payload["contract_probe_audit"]["failed_gates"] == payload["failed_gates"]
    assert (
        payload["contract_probe_audit"]["failure_evidence"]
        == payload["failure_evidence"]
    )
    assert payload["failure_evidence"]["probe_exception"]["exception_type"] == (
        "RuntimeError"
    )
    assert (
        "provider timeout"
        in payload["failure_evidence"]["probe_exception"]["exception_message"]
    )
