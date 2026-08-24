from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pytest

from scripts.slurm import qasper_debug_contract_probe as probe
from scripts.slurm.validate_qasper_contract_probe import validate_contract_probe


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self.text = json.dumps(payload, separators=(",", ":"))
        self.additional_kwargs = {"finish_reason": "stop"}


class _Provider:
    """A schema-driven provider double; production parsers still own all state."""

    def __init__(self, case: probe.ProbeCase, *, reject_fault: bool = True) -> None:
        self.case = case
        self.reject_fault = reject_fault
        # The production question proposition has these three applicable
        # bindings; the fake is a separate auditor instance and therefore
        # cannot read proposal-instance state.
        self._slots: list[str] = ["actor", "predicate", "object"]
        self._fragment = ""

    def __call__(self, messages: object, **kwargs: object) -> _Response:
        response_format = kwargs["response_format"]
        schema = response_format["json_schema"]  # type: ignore[index]
        name = schema["name"]  # type: ignore[index]
        if name == "qasper_typed_candidate":
            return _Response(
                {
                    "candidate": self.case.controlled_candidate
                    or self.case.expected_candidate
                }
            )
        if name == "semantic_evidence_set_proposition":
            return self._proposal(schema)  # type: ignore[arg-type]
        if name == "candidate_bound_unknown_audit":
            return self._unknown_audit(schema)  # type: ignore[arg-type]
        if name == "semantic_entailment_audit":
            return self._entailment_audit(schema)  # type: ignore[arg-type]
        raise AssertionError(f"unexpected production schema {name!r}")

    def _proposal(self, schema: dict[str, object]) -> _Response:
        proposal_judgment = self.case.proposal_judgment or self.case.expected_judgment
        schema_body = schema["schema"]  # type: ignore[index]
        branches = schema_body["oneOf"]  # type: ignore[index]
        branch = next(
            branch
            for branch in branches
            if branch["properties"]["candidate_judgment"]["enum"] == [proposal_judgment]
        )
        premise_schema = branch["properties"]["premises"]["items"]
        evidence_slot_ids = premise_schema["properties"]["supports_slot_ids"]["items"][
            "enum"
        ]
        proposition_slots = premise_schema["properties"]["binds_proposition_slots"][
            "items"
        ]["enum"]
        self._slots = list(proposition_slots)
        selector_match = re.search(r"E\d+:S\d+", str(self._last_message))
        selector = selector_match.group(0) if selector_match else "E1:S1"
        self._fragment = (
            "The authors released code for a different baseline"
            if self.case.case_id == "auditor_fail"
            else self.case.evidence
        )
        if proposal_judgment == "unknown":
            relation = "undetermined"
        elif self.case.expected_candidate == "yes":
            relation = (
                "proposition_support"
                if proposal_judgment == "supported"
                else "explicit_contradiction"
            )
        else:
            relation = (
                "explicit_contradiction"
                if proposal_judgment == "supported"
                else "proposition_support"
            )
        payload: dict[str, object] = {
            "candidate_judgment": proposal_judgment,
            "evidence_relation": relation,
            "support_mode": "evidence_set",
            "proof_mode": (
                "none" if proposal_judgment == "unknown" else "atomic_semantic"
            ),
            "jointly_complete": proposal_judgment != "unknown",
            "each_premise_required": proposal_judgment != "unknown",
            "premises": [],
            "not_applicable_proposition_slots": [
                slot
                for slot in ("actor", "predicate", "object", "quantifier")
                if slot not in proposition_slots
            ],
        }
        if proposal_judgment == "unknown":
            payload["unknown_assessment"] = {
                "reviewed_span_selectors": [selector],
                "unresolved_proposition_slots": list(proposition_slots),
                "support_gap": "The evidence does not establish the proposition.",
                "contradiction_gap": "The evidence does not explicitly contradict it.",
            }
        else:
            payload["premises"] = [
                {
                    "span_selector": selector,
                    "proposition_fragment": self._fragment,
                    "supports_slot_ids": list(evidence_slot_ids),
                    "binds_proposition_slots": list(proposition_slots),
                }
            ]
        return _Response(payload)

    def _entailment_audit(self, schema: dict[str, object]) -> _Response:
        properties = schema["schema"]["properties"]  # type: ignore[index]
        passed = self.case.expected_audit_status == "passed" or not self.reject_fault
        checks: list[dict[str, object]] = []
        checks.append(
            {
                "premise_ref": "P1",
                "fragment_entailed": passed,
                "scope_consistent": passed,
                "proposition_bindings_valid": passed,
                "evidence_relation_valid": passed,
                "declared_proposition_slots": list(self._slots),
                "proposition_slot_checks": [
                    {"slot": slot, "binding_valid": passed, "evidence_text": "The"}
                    for slot in self._slots
                ],
            }
        )
        conclusion = {
            field: passed
            for field in (
                "conclusion_entailed",
                "actor_consistent",
                "predicate_consistent",
                "object_consistent",
                "polarity_consistent",
                "quantifier_consistent",
                "scope_consistent",
            )
        }
        # Touch the schema so this double cannot silently drift to a made-up
        # response shape if the production contract changes.
        assert "premise_checks" in properties
        return _Response(
            {
                "premise_checks": checks,
                "jointly_entails": passed,
                "each_premise_required": passed,
                "contradiction_free": passed,
                "conclusion_check": conclusion,
            }
        )

    def _unknown_audit(self, schema: dict[str, object]) -> _Response:
        del schema
        return _Response(
            {
                "audit_scope": "original_candidate_and_verifier_unknown_only",
                "audited_candidate": self.case.expected_candidate,
                "audited_verdict": "insufficient_evidence",
                "audited_judgment": "unknown",
                "typed_conclusion_present": True,
                "reviewed_evidence_present": True,
                "support_gap_valid": True,
                "contradiction_gap_valid": True,
                "relationship_consistent": True,
                "replacement_candidate_allowed": False,
                "replacement_candidate": "",
            }
        )

    @property
    def _last_message(self) -> str:
        # The production wrapper passes each request directly.  The selector is
        # always E1:S1 for the one packed span; this property keeps the fake
        # independent of private prompt construction.
        return "E1:S1"


def _factory(*, case_id: str, **_: object) -> _Provider:
    case = next(case for case in probe._PROBE_CASES if case.case_id == case_id)
    return _Provider(case)


def _assert_live_state_coverage(rows: list[dict[str, Any]]) -> None:
    assert len(rows) == 6
    assert {row["quality_lane_excluded"] for row in rows} == {True}
    assert {probe._observed_state(row)[0] for row in rows} >= {"no"}
    assert {probe._observed_state(row)[1] for row in rows} >= {
        "contradicted",
        "unknown",
    }
    assert {probe._observed_state(row)[2] for row in rows} == {"passed", "failed"}


def _assert_controlled_candidate_identity(rows: list[dict[str, Any]]) -> None:
    contradicted = next(
        row for row in rows if row["example_id"] == "contract-probe-contradicted_yes"
    )
    assert contradicted["controlled_input"]["mode"] == "controlled_original_candidate"
    assert contradicted["controlled_input"]["generator_candidate"] == "yes"
    assert contradicted["controlled_input"]["original_candidate"] == "yes"
    assert (
        contradicted["evidence_metadata"]["qasper_candidate_generation"][
            "typed_candidate"
        ]
        == "yes"
    )
    assert (
        contradicted["evidence_metadata"]["qasper_candidate_generation"][
            "candidate_input_mode"
        ]
        == "controlled_contract_probe"
    )
    controlled_stack = contradicted["evidence_metadata"]["qasper_candidate_generation"][
        "message_stack"
    ]
    assert "CONTROLLED ORIGINAL CANDIDATE UNDER AUDIT" in controlled_stack[1]["content"]
    assert (
        contradicted["evidence_metadata"]["semantic_proposition_verifier"][
            "candidate_label"
        ]
        == "yes"
    )
    contradicted_authority = contradicted["evidence_metadata"][
        "semantic_proposition_authority"
    ]
    assert contradicted_authority["required_slot_ids"] == [
        "support:boolean_proposition"
    ]
    assert contradicted_authority["verified_slot_ids"] == [
        "support:boolean_proposition"
    ]


def _assert_provider_call_and_span_evidence(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        assert len(row["contract_probe_live_calls"]) >= 3
        assert "probe:E1:S1" not in json.dumps(row)
        verifier = row["evidence_metadata"]["semantic_proposition_verifier"]
        assert verifier["audit_model_call_count"] > 0
        events = verifier["debug_trace"]["events"]
        assert events
        assert any(
            (event.get("transaction") or {}).get("audit", {}).get("attempts")
            for event in events
        )
        packed = events[-1]["packed_evidence"]
        source_text = row["evidence_bundle"]["items"][0]["text"]
        assert packed[0]["selectors"][0]["text"] == source_text
        assert packed[0]["selectors"][0]["span_end"] == len(source_text)


def _assert_real_auditor_failure(rows: list[dict[str, Any]]) -> None:
    auditor_fail = next(
        row for row in rows if row["example_id"] == "contract-probe-auditor_fail"
    )
    assert (
        auditor_fail["evidence_metadata"]["contract_probe_controlled_proposal"][
            "contract_id"
        ]
        == "qasper_controlled_verifier_negative_probe.v1"
    )
    fail_event = auditor_fail["evidence_metadata"]["semantic_proposition_verifier"][
        "debug_trace"
    ]["events"][-1]
    parsed_proposal = fail_event["transaction"]["proposal"]["attempts"][-1][
        "parsed_value"
    ]
    assert parsed_proposal["candidate_judgment"] == "supported"
    assert fail_event["transaction"]["audit"]["attempts"]


def test_live_probe_uses_production_parser_and_auditor() -> None:
    rows = probe.run_live_probes(
        "http://provider.invalid/v1",
        "contract-probe-model",
        model_factory=_factory,
    )

    _assert_live_state_coverage(rows)
    _assert_controlled_candidate_identity(rows)
    _assert_provider_call_and_span_evidence(rows)
    _assert_real_auditor_failure(rows)


def test_provider_state_mismatch_fails_closed() -> None:
    # Alter the returned response without altering the control expectation.
    class WrongProvider(_Provider):
        def __call__(self, messages: object, **kwargs: object) -> _Response:
            value = super().__call__(messages, **kwargs)
            if kwargs["response_format"]["json_schema"]["name"] == "qasper_typed_candidate" and self.case.case_id == "supported_no":  # type: ignore[index]
                return _Response({"candidate": "yes"})
            return value

    def factory(*, case_id: str, **kwargs: object) -> WrongProvider:
        case = next(case for case in probe._PROBE_CASES if case.case_id == case_id)
        return WrongProvider(case)

    with pytest.raises(RuntimeError, match="provider observed"):
        probe.run_live_probes(
            "http://provider.invalid/v1", "model", model_factory=factory
        )


def test_controlled_fault_requires_actual_auditor_rejection() -> None:
    def passing_fault_factory(*, case_id: str, **kwargs: object) -> _Provider:
        case = next(case for case in probe._PROBE_CASES if case.case_id == case_id)
        return _Provider(case, reject_fault=False)

    with pytest.raises(RuntimeError, match="provider observed"):
        probe.run_live_probes(
            "http://provider.invalid/v1",
            "model",
            model_factory=passing_fault_factory,
        )


def test_probe_write_replaces_artifact_without_duplicate_rows(tmp_path: Path) -> None:
    path = tmp_path / "contract_probe_predictions.jsonl"
    rows = [{"example_id": "one"}, {"example_id": "two"}]
    probe._write_rows(path, rows)
    probe._write_rows(path, rows)
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


def test_live_stage_probe_rows_pass_formal_provider_audit(tmp_path: Path) -> None:
    rows = probe.run_live_probes(
        "http://provider.invalid/v1",
        "contract-probe-model",
        model_factory=_factory,
    )
    predictions = tmp_path / "contract_probe_predictions.jsonl"
    audit_path = tmp_path / "contract_probe_audit.json"
    probe._write_rows(predictions, rows)

    audit = validate_contract_probe(predictions, output_path=audit_path)

    assert audit["status"] == "passed"
    assert audit["failed_gates"] == []
    assert audit["behavior_violations"] == []
