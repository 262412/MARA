from __future__ import annotations

import json
from pathlib import Path

FIXTURE = (
    Path(__file__).parent / "fixtures" / "qasper_trace_canary_10388470_stage8.json"
)


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_job_10388470_freezes_the_exact_candidate_response_and_parse() -> None:
    payload = _fixture()
    response = payload["online_candidate_response"]

    assert payload["source"]["job_id"] == "10388470"
    assert response["raw_response"] == '{\n\n\n    "candidate": "yes"\n}'
    assert response["raw_response_digest"] == (
        "49ee055255d2866e25ef3b503cc43b9f5055b5e2ff67f518c443c45b393f5148"
    )
    assert response["status"] == "parsed"
    assert response["typed_candidate"] == "yes"


def test_job_10388470_freezes_the_typed_stop_before_proposal() -> None:
    payload = _fixture()
    stop = payload["online_verifier_stop"]

    assert stop["status"] == "failed"
    assert stop["candidate_verification_status"] == "pre_audit_failed"
    assert stop["audit_status"] == "not_started"
    assert stop["proposal_transaction"] == {}
    assert stop["reason"] == "release_conclusion_auditor_not_independent"


def test_job_10388470_freezes_the_two_independent_trace_defects() -> None:
    payload = _fixture()
    failure = payload["observed_stage8_failure"]

    assert failure["stage_index"] == 8
    assert failure["reference_incompleteness_reasons"] == [
        "proposal_attempt_missing"
    ]
    assert failure["local_incompleteness_reasons"] == [
        "candidate_raw_response_missing",
        "proposal_attempt_missing",
    ]
    assert payload["root_cause"] == (
        "replay_dropped_the_frozen_candidate_response_and_trace_required_a_proposal_"
        "after_a_typed_pre_audit_stop"
    )
