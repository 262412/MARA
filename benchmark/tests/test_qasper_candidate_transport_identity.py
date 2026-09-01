from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from benchmark.tests.test_qasper_contract_probe_generation import (
    _message_text,
    _Provider,
    _Response,
)
from scripts.slurm import qasper_debug_contract_probe as probe
from scripts.slurm.validate_qasper_contract_probe import validate_contract_probe


def test_provider_state_mismatch_fails_closed(tmp_path: Path) -> None:
    class WrongProvider(_Provider):
        def __call__(self, messages: object, **kwargs: object) -> _Response:
            value = super().__call__(messages, **kwargs)
            response_format = kwargs.get("response_format")
            response_format = (
                response_format if isinstance(response_format, dict) else {}
            )
            schema = response_format.get("json_schema")
            schema = schema if isinstance(schema, dict) else {}
            if schema.get(
                "name"
            ) == "qasper_typed_candidate" and "CONTROLLED ORIGINAL CANDIDATE UNDER AUDIT:\nyes" in _message_text(
                messages
            ):
                return _Response({"candidate": "no"})
            return value

    def factory(*, case_id: str, **kwargs: object) -> WrongProvider:
        del case_id, kwargs
        return WrongProvider()

    predictions = tmp_path / "contract_probe_predictions.jsonl"
    audit_path = tmp_path / "contract_probe_audit.json"
    with pytest.raises(RuntimeError, match="candidate_transport"):
        probe.run_live_probes(
            "http://provider.invalid/v1",
            "model",
            auditor_base_url="http://auditor.invalid/v1",
            auditor_model="heterogeneous-auditor-model",
            model_factory=factory,
            output_path=predictions,
            audit_path=audit_path,
        )

    rows = [json.loads(line) for line in predictions.read_text().splitlines()]
    failed = next(
        row for row in rows if row["example_id"] == "contract-probe-contradicted_yes"
    )
    _assert_transport_failure(failed)
    with pytest.raises(ValueError, match="provider contract probe failed"):
        validate_contract_probe(predictions, output_path=audit_path)
    formal_audit = json.loads(audit_path.read_text())
    mismatch_gate = "qasper_controlled_candidate_transport_mismatch_count"
    assert formal_audit["debug_gate_metrics"][mismatch_gate] > 0
    assert formal_audit["hard_gates"][mismatch_gate]["passed"] is False


def _assert_transport_failure(failed: dict[str, Any]) -> None:
    controlled = failed["controlled_input"]
    assert controlled["candidate_transport_failure"] == "candidate_transport_failed"
    assert controlled["requested_candidate"] == "yes"
    assert controlled["provider_raw_candidate"] == "no"
    assert controlled["cleaned_candidate"] == "no"
    assert controlled["typed_candidate"] == "no"
    assert controlled["verifier_input_candidate"] == ""
    assert controlled["verifier_transport_status"] == "verifier_not_started"
    assert controlled["auditor_transport_status"] == "auditor_not_started"
    assert controlled["transport_identity_preserved"] is False
    assert len(failed["contract_probe_live_calls"]) == 1
    assert "semantic_proposition_verifier" not in failed["evidence_metadata"]
    assert failed["engine_terminal_commit"]["outcome"] == "execution_failed"
    assert failed["engine_terminal_commit"]["outcome_reason"] == (
        "candidate_transport_failed"
    )
