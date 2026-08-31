from __future__ import annotations

import json
from pathlib import Path


FIXTURE = (
    Path(__file__).parent / "fixtures" / "qasper_trace_canary_10388470_stage9.json"
)


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_job_10388470_freezes_the_zero_call_typed_pre_audit_stop() -> None:
    payload = _fixture()
    execution = payload["online_verifier_execution"]

    assert payload["source"]["job_id"] == "10388470"
    assert execution["status"] == "failed"
    assert execution["candidate_verification_status"] == "pre_audit_failed"
    assert execution["auditor_relationship"] == "distinct_instance_same_model"
    assert execution["proposal_model_call_count"] == 0
    assert execution["audit_model_call_count"] == 0
    assert execution["actual_model_call_count"] == 0
    assert execution["transaction"] == {}
    assert execution["reason"] == "release_conclusion_auditor_not_independent"


def test_job_10388470_freezes_the_stage_nine_classification_defect() -> None:
    payload = _fixture()
    stage = payload["observed_stage9"]

    assert stage["stage_index"] == 9
    assert stage["stage"] == "verifier_and_auditor"
    assert stage["incompleteness_reasons"] == ["verifier_input_missing"]
    assert stage["reference_comparison_digest"] == stage["local_comparison_digest"]
    assert payload["root_cause"] == (
        "stage_nine_treated_an_explicit_zero_call_typed_pre_audit_stop_as_a_"
        "missing_verifier_input"
    )
