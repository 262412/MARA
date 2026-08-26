from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmark.tests.qasper_contract_probe_provider_support import (
    _AUDITOR_BASE_URL,
    _AUDITOR_MODEL,
)
from benchmark.tests.test_qasper_contract_probe_generation import _Provider
from scripts.slurm import qasper_debug_contract_probe as probe
from scripts.slurm.validate_qasper_contract_probe import validate_contract_probe


def test_same_model_provider_is_rejected_before_any_provider_call(
    tmp_path: Path,
) -> None:
    factory_calls: list[dict[str, object]] = []

    def factory(**kwargs: object) -> _Provider:
        factory_calls.append(dict(kwargs))
        return _Provider()

    with pytest.raises(ValueError, match="same model/provider"):
        probe.run_live_probes(
            "http://provider.invalid/v1",
            "Qwen/Qwen3-8B",
            auditor_base_url="http://provider.invalid/v1",
            auditor_model="qwen/qwen3-8b",
            model_factory=factory,
            output_path=tmp_path / "predictions.jsonl",
            audit_path=tmp_path / "audit.json",
        )

    assert factory_calls == []
    audit = json.loads((tmp_path / "audit.json").read_text(encoding="utf-8"))
    gate = audit["hard_gates"]["qasper_contract_probe_provider_heterogeneity_complete"]
    assert gate["passed"] is False


def test_separate_auditor_configuration_is_used_and_recorded() -> None:
    factory_calls: list[dict[str, object]] = []

    def factory(**kwargs: object) -> _Provider:
        factory_calls.append(dict(kwargs))
        return _Provider()

    rows = probe.run_live_probes(
        "http://provider.invalid/v1",
        "contract-probe-model",
        auditor_base_url=_AUDITOR_BASE_URL,
        auditor_model=_AUDITOR_MODEL,
        model_factory=factory,
    )

    assert {
        (call["role"], call["base_url"], call["model"]) for call in factory_calls
    } == {
        (
            "candidate_and_proposal",
            "http://provider.invalid/v1",
            "contract-probe-model",
        ),
        ("auditor", _AUDITOR_BASE_URL, _AUDITOR_MODEL),
    }
    for row in rows:
        calls = row["contract_probe_live_calls"]
        assert {
            (call["provider_role"], call["base_url"], call["model"]) for call in calls
        } == {
            ("proposer", "http://provider.invalid/v1", "contract-probe-model"),
            ("auditor", _AUDITOR_BASE_URL, _AUDITOR_MODEL),
        }
        verifier = row["evidence_metadata"]["semantic_proposition_verifier"]
        assert verifier["auditor_relationship"] == "distinct_model"
        assert verifier["model"] == "contract-probe-model"
        assert verifier["audit_model"] == _AUDITOR_MODEL


def test_formal_provider_audit_rejects_same_model_aliases(tmp_path: Path) -> None:
    rows = probe.run_live_probes(
        "http://provider.invalid/v1",
        "contract-probe-model",
        auditor_base_url=_AUDITOR_BASE_URL,
        auditor_model=_AUDITOR_MODEL,
        model_factory=lambda **_: _Provider(),
    )
    for row in rows:
        for call in row["contract_probe_live_calls"]:
            call["base_url"] = "http://provider.invalid/v1"
            call["model"] = "Qwen/Qwen3-8B"
            call["provider_identity"] = {
                "base_url": "http://provider.invalid/v1",
                "model": "Qwen/Qwen3-8B",
                "role": call["provider_role"],
            }
        verifier = row["evidence_metadata"]["semantic_proposition_verifier"]
        verifier["model"] = "Qwen/Qwen3-8B"
        verifier["audit_model"] = "Qwen/Qwen3-8B"
        verifier["auditor_relationship"] = "distinct_instance_same_model"
        row["evidence_metadata"]["contract_probe_provider_identities"] = {
            role: [
                {
                    "base_url": "http://provider.invalid/v1",
                    "model": "Qwen/Qwen3-8B",
                    "role": role,
                }
            ]
            for role in ("proposer", "auditor")
        }
    predictions = tmp_path / "contract_probe_predictions.jsonl"
    audit_path = tmp_path / "contract_probe_audit.json"
    probe._write_rows(predictions, rows)

    with pytest.raises(ValueError, match="provider contract probe failed"):
        validate_contract_probe(predictions, output_path=audit_path)

    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    gate = audit["hard_gates"]["qasper_contract_probe_provider_heterogeneity_complete"]
    assert gate["passed"] is False
    assert any(
        "provider_identity_same_model" in failure["violations"]
        for failure in audit["provider_identity_violations"]
    )
