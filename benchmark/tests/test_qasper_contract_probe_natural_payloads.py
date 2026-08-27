from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmark.tests.qasper_contract_probe_provider_support import (
    NATURAL_QUALITY_PAYLOAD_FIXTURES,
    natural_quality_payload_fixture,
)
from benchmark.tests.test_qasper_contract_probe_generation import _evidence_span
from benchmark.tests.test_qasper_contract_probe_generation import (
    _factory as _live_factory,
)
from benchmark.tests.test_qasper_contract_probe_generation import (
    _Provider,
    _Response,
    _structured_candidate,
)
from scripts.slurm import qasper_debug_contract_probe as probe
from scripts.slurm.qasper_debug_contract_pre_audit_provider import (
    controlled_pre_audit_model_factory,
)
from scripts.slurm.qasper_debug_contract_probe_cases import (
    NATURAL_QUALITY_PRE_AUDIT_CASES,
)
from scripts.slurm.validate_qasper_contract_probe import validate_contract_probe

_PROPOSER_BASE_URL = "http://natural-proposer.invalid/v1"
_PROPOSER_MODEL = "natural-quality-proposer-model"
_AUDITOR_BASE_URL = "http://natural-auditor.invalid/v1"
_AUDITOR_MODEL = "natural-quality-auditor-model"

_FIXTURE_BY_CASE = {
    case.case_id: case.payload_fixture for case in NATURAL_QUALITY_PRE_AUDIT_CASES
}


class _NaturalQualityProvider(_Provider):
    """Generate one natural-quality-derived invalid proposal payload."""

    controlled_pre_audit = True

    def __init__(self, fixture_id: str) -> None:
        super().__init__()
        self.fixture_id = fixture_id

    def _proposal(self, messages: object, schema: dict[str, object]) -> _Response:
        text = _message_text(messages)
        candidate = _structured_candidate(text)
        selector, evidence_text = _evidence_span(text)
        payload = natural_quality_payload_fixture(
            self.fixture_id,
            schema,
            candidate=candidate,
            selector=selector,
            evidence_text=evidence_text,
        )
        return _Response(payload)


def _message_text(messages: object) -> str:
    if not isinstance(messages, (list, tuple)) or not messages:
        raise RuntimeError("natural-quality provider message stack missing")
    contents: list[str] = []
    for message in messages:
        content = (
            message.get("content")
            if isinstance(message, dict)
            else getattr(message, "content", None)
        )
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("natural-quality provider message content missing")
        contents.append(content)
    return "\n\n".join(contents)


def _factory(*, case_id: str, **_: object) -> _NaturalQualityProvider:
    fixture_id = _FIXTURE_BY_CASE.get(case_id)
    if not fixture_id:
        raise RuntimeError(f"natural-quality fixture missing for case {case_id}")
    return _NaturalQualityProvider(fixture_id)


def test_natural_quality_payload_fixture_catalog_matches_pre_audit_cases() -> None:
    case_fixtures = {case.payload_fixture for case in NATURAL_QUALITY_PRE_AUDIT_CASES}
    catalog_fixtures = {
        fixture.fixture_id for fixture in NATURAL_QUALITY_PAYLOAD_FIXTURES
    }
    assert case_fixtures == catalog_fixtures
    assert len(case_fixtures) == 4


def test_natural_quality_invalid_proposals_fail_before_auditor() -> None:
    rows = probe.run_pre_audit_probes(
        _PROPOSER_BASE_URL,
        _PROPOSER_MODEL,
        auditor_base_url=_AUDITOR_BASE_URL,
        auditor_model=_AUDITOR_MODEL,
        model_factory=_factory,
    )

    assert {
        row["example_metadata"]["contract_probe_case"]["case_id"] for row in rows
    } == {case.case_id for case in NATURAL_QUALITY_PRE_AUDIT_CASES}
    for row in rows:
        assert row["gold_answers"] == []
        verifier = row["evidence_metadata"]["semantic_proposition_verifier"]
        assert verifier["candidate_verification_status"] == "pre_audit_failed"
        assert verifier["audit_status"] == "not_started"
        assert verifier["candidate_verification_audit"]["status"] == "not_started"
        assert verifier["candidate_verification_audit"]["classification"] == (
            "pre_audit_failed"
        )
        assert verifier["audit_model_call_count"] == 0
        assert not [
            call
            for call in row["contract_probe_live_calls"]
            if call["provider_role"] == "auditor"
        ]
        assert row["engine_terminal_answer"] == "unanswerable"
        assert row["engine_terminal_commit"]["outcome"] == "execution_failed"


def test_natural_quality_payload_mutations_are_visible_in_proposal_trace() -> None:
    rows = probe.run_pre_audit_probes(
        _PROPOSER_BASE_URL,
        _PROPOSER_MODEL,
        auditor_base_url=_AUDITOR_BASE_URL,
        auditor_model=_AUDITOR_MODEL,
        model_factory=_factory,
    )

    by_fixture = {
        row["example_metadata"]["contract_probe_case"]["payload_fixture"]: row
        for row in rows
    }
    overdeclared = by_fixture["proposer_over_declares_actor_quantifier"]
    duplicate = by_fixture["unknown_assessment_duplicate_unresolved_slots"]
    over_trace = overdeclared["evidence_metadata"]["semantic_proposition_verifier"]
    duplicate_trace = duplicate["evidence_metadata"]["semantic_proposition_verifier"]
    assert over_trace["parse_failure_reason"] == "premise_proposition_binding_invalid"
    assert duplicate_trace["parse_failure_reason"] == "unknown_assessment_slot_invalid"

    def proposal_payload(row: dict[str, Any]) -> dict[str, Any]:
        verifier = row["evidence_metadata"]["semantic_proposition_verifier"]
        events = verifier["debug_trace"]["events"]
        transaction = events[-1]["transaction"]
        attempt = transaction["proposal"]["attempts"][-1]
        return json.loads(attempt["raw_response"])

    over_premise = proposal_payload(overdeclared)["premises"][0]
    assert {"actor", "quantifier"} <= set(over_premise["binds_proposition_slots"])
    duplicate_assessment = proposal_payload(duplicate)["unknown_assessment"]
    unresolved = duplicate_assessment["unresolved_proposition_slots"]
    assert unresolved == "actor|actor"

    title = by_fixture["title_only_span_binds_relation_object"]
    title_item = title["evidence_bundle"]["items"][0]
    assert title_item["element_type"] == "title"
    title_premise = proposal_payload(title)["premises"][0]
    assert {"predicate", "object"} <= set(title_premise["binds_proposition_slots"])
    title_proposal = title["evidence_metadata"]["semantic_proposition_verifier"]
    title_reasons = {
        str(title_proposal.get(field) or "")
        for field in (
            "audit_reason",
            "parse_failure_reason",
            "audit_parse_failure_reason",
        )
    }
    assert title_reasons & {
        "pre_audit_slot_evidence_mismatch",
        "local_semantic_relation_mention_only",
        "local_semantic_slot_span_unbound",
    }

    mismatch = by_fixture[
        "proposer_slot_expectations_differ_from_verified_slot_evidence"
    ]
    mismatch_premise = proposal_payload(mismatch)["premises"][0]
    assert set(mismatch_premise["binds_proposition_slots"]) == {
        "actor",
        "predicate",
        "object",
    }
    assert mismatch["evidence_bundle"]["items"][0]["text"].endswith("released it.")


def test_formal_probe_audit_requires_independent_four_case_pre_audit_channel(
    tmp_path: Path,
) -> None:
    live_rows = probe.run_live_probes(
        _PROPOSER_BASE_URL,
        _PROPOSER_MODEL,
        auditor_base_url=_AUDITOR_BASE_URL,
        auditor_model=_AUDITOR_MODEL,
        model_factory=_live_factory,
    )
    # Use the production controlled provider for the formal pre-audit lane.
    pre_audit_rows = probe.run_pre_audit_probes(
        _PROPOSER_BASE_URL,
        _PROPOSER_MODEL,
        auditor_base_url=_AUDITOR_BASE_URL,
        auditor_model=_AUDITOR_MODEL,
        model_factory=controlled_pre_audit_model_factory,
    )
    live_path = tmp_path / "contract_probe_predictions.jsonl"
    pre_audit_path = tmp_path / "contract_pre_audit_predictions.jsonl"
    audit_path = tmp_path / "contract_probe_audit.json"
    probe._write_rows(live_path, live_rows)
    probe._write_rows(pre_audit_path, pre_audit_rows)

    audit = validate_contract_probe(
        live_path,
        output_path=audit_path,
        pre_audit_predictions_path=pre_audit_path,
    )

    assert audit["status"] == "passed"
    assert audit["prediction_count"] == 6
    assert audit["pre_audit_channel"]["prediction_count"] == 4
    assert audit["pre_audit_channel"]["status"] == "passed"
    assert audit["pre_audit_channel"]["auditor_model_call_count"] == 0
    assert (
        audit["hard_gates"]["qasper_contract_probe_pre_audit_case_coverage_complete"][
            "passed"
        ]
        is True
    )
    assert (
        audit["hard_gates"]["qasper_contract_probe_pre_audit_terminalization_complete"][
            "passed"
        ]
        is True
    )
