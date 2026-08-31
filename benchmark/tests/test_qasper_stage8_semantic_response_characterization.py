from __future__ import annotations

import json
from pathlib import Path

from ktem.reasoning.mara_candidate_unknown_audit import parse_candidate_unknown_audit

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "qasper_trace_10385302_stage8_semantic_responses.json"
)


def _fixture() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_job_10385302_freezes_the_low_entropy_proposal_response() -> None:
    payload = _fixture()
    proposal = payload["proposal"]
    parsed = json.loads(proposal["raw_response"])

    assert payload["source"]["job_id"] == "10385302"
    assert set(parsed) == {
        "candidate_judgment",
        "canonical_evidence_plan_id",
    }
    assert parsed["candidate_judgment"] == "supported"
    assert canonical_digest(proposal["raw_response"]) == proposal["raw_response_digest"]
    assert proposal["status"] == "parsed"
    assert proposal["parse_failure_reason"] == ""


def test_job_10385302_freezes_the_independent_audit_response() -> None:
    payload = _fixture()
    audit = payload["audit"]
    parsed = json.loads(audit["raw_response"])

    assert set(parsed) == {
        "premise_checks",
        "jointly_entails",
        "each_premise_required",
        "contradiction_free",
        "conclusion_check",
    }
    assert set(parsed["premise_checks"]) == {"P1", "P2"}
    assert parsed["jointly_entails"] is False
    assert canonical_digest(audit["raw_response"]) == audit["raw_response_digest"]
    assert audit["status"] == "parsed"
    assert audit["parse_failure_reason"] == ""


def test_stage_eight_requires_local_reparse_not_frozen_parsed_authority() -> None:
    payload = _fixture()

    assert payload["proposal"]["parsed_value_digest"] != canonical_digest({})
    assert payload["audit"]["parsed_value_digest"] != canonical_digest({})
    assert payload["invariant"] == (
        "semantic_proposal_and_audit_raw_responses_are_reparsed_against_"
        "local_frozen_authority"
    )


def test_job_10385302_freezes_the_candidate_unknown_audit_variant() -> None:
    audit = _fixture()["unknown_audit"]

    parsed = parse_candidate_unknown_audit(
        audit["raw_response"],
        candidate="yes",
        verifier_judgment="unknown",
    )

    assert audit["example_id"] == "e330e162ec29722f5ec9f83853d129c9e0693d65"
    assert canonical_digest(audit["raw_response"]) == audit["raw_response_digest"]
    assert parsed.failure_reason == ""
    assert parsed.value is not None
    assert canonical_digest(parsed.value) == audit["parsed_value_digest"]
