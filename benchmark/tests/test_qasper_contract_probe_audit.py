from __future__ import annotations

import json

import pytest

from benchmark.tests.qasper_contract_probe_provider_support import (
    _AUDITOR_BASE_URL,
    _AUDITOR_MODEL,
)
from benchmark.tests.qasper_debug_contract_fixtures import _qasper_debug_prediction
from benchmark.tests.test_qasper_contract_probe_generation import _factory
from scripts.slurm import qasper_debug_contract_probe as probe
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
    assert (
        audit["debug_gate_metrics"][
            "qasper_candidate_verifier_auditor_label_set_mismatch_count"
        ]
        == 0.0
    )
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


def test_auditor_parse_failure_does_not_satisfy_live_coverage() -> None:
    rows = probe.run_live_probes(
        "http://provider.invalid/v1",
        "contract-probe-model",
        auditor_base_url=_AUDITOR_BASE_URL,
        auditor_model=_AUDITOR_MODEL,
        model_factory=_factory,
    )
    auditor_fail = next(
        row for row in rows if row["example_id"] == "contract-probe-auditor_fail"
    )
    verifier = auditor_fail["evidence_metadata"]["semantic_proposition_verifier"]
    audit_stage = verifier["debug_trace"]["events"][-1]["transaction"]["audit"]
    audit_stage["status"] = "parse_failed"
    audit_attempt = audit_stage["attempts"][-1]
    audit_attempt["parsed_value"] = None
    audit_attempt["parse_failure_reason"] = "json_decode_error"

    with pytest.raises(RuntimeError, match="semantic auditor rejection"):
        probe._assert_live_coverage(rows)


def test_provider_audit_reconciles_behavior_failure_across_status_and_evidence(
    tmp_path,
) -> None:
    rows = probe.run_live_probes(
        "http://provider.invalid/v1",
        "contract-probe-model",
        auditor_base_url=_AUDITOR_BASE_URL,
        auditor_model=_AUDITOR_MODEL,
        model_factory=_factory,
    )
    auditor_fail = next(
        row for row in rows if row["example_id"] == "contract-probe-auditor_fail"
    )
    verifier = auditor_fail["engine_terminal_evidence_bundle"]["metadata"][
        "semantic_proposition_verifier"
    ]
    verifier["explicit_contradiction"] = True
    predictions = tmp_path / "contract_probe_predictions.jsonl"
    audit_path = tmp_path / "contract_probe_audit.json"
    probe._write_rows(predictions, rows)

    with pytest.raises(ValueError, match="provider contract probe failed"):
        validate_contract_probe(predictions, output_path=audit_path)

    audit = json.loads(audit_path.read_text())
    lane = audit["contract_probe_audit"]
    assert audit["status"] == "failed"
    assert lane["status"] == "failed"
    assert audit["failed_gates"]
    assert audit["failed_gates"] == lane["failed_gates"]
    assert audit["behavior_violations"]
    assert (
        lane["failure_evidence"]["behavior_violations"] == audit["behavior_violations"]
    )
