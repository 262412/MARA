from __future__ import annotations

from benchmark.tests.qasper_debug_contract_fixtures import _qasper_debug_prediction
from scripts.slurm import qasper_debug_contract_audit as audit


def test_quality_auditor_rejection_is_not_hidden_by_safe_abstention_exemption() -> None:
    prediction = _qasper_debug_prediction("example-5", "controller_auto")
    prediction["qasper_debug_lane"] = "quality"
    verifier = prediction["evidence_metadata"]["semantic_proposition_verifier"]
    verifier["audit_status"] = "rejected"
    candidate_audit = verifier["candidate_verification_audit"]

    failed, rejected = audit._semantic_audit_failure_flags(
        verifier,
        candidate_audit,
        prediction,
    )

    assert failed or rejected


def test_controlled_negative_safe_abstention_remains_exempt() -> None:
    prediction = _qasper_debug_prediction("example-5", "controller_auto")
    prediction["qasper_debug_lane"] = "contract_probe"
    prediction["expected_negative_probe"] = True
    prediction["contract_probe_expectation"] = "auditor_fail"
    verifier = prediction["evidence_metadata"]["semantic_proposition_verifier"]
    verifier["audit_status"] = "rejected"
    candidate_audit = verifier["candidate_verification_audit"]

    assert audit._semantic_audit_failure_flags(
        verifier,
        candidate_audit,
        prediction,
    ) == (False, False)


def test_unlabelled_safe_abstention_does_not_hide_auditor_rejection() -> None:
    prediction = _qasper_debug_prediction("example-5", "controller_auto")
    verifier = prediction["evidence_metadata"]["semantic_proposition_verifier"]
    verifier["audit_status"] = "rejected"
    candidate_audit = verifier["candidate_verification_audit"]

    failed, rejected = audit._semantic_audit_failure_flags(
        verifier,
        candidate_audit,
        prediction,
    )

    assert failed or rejected
