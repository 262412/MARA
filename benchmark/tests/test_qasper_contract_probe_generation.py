from __future__ import annotations

import json
import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from benchmark.tests.qasper_contract_probe_provider_support import (  # noqa: F401
    _audit_entails_proposal,
    _audit_payload,
    _candidate_selector_refs,
    _evidence_signal,
    _normalize_text,
    _proposal_payload,
    _run_probe,
    _schema_body,
    _schema_branch,
    _schema_enum,
    _schema_properties,
    _schema_required,
    _schema_shape,
)
from scripts.slurm import qasper_debug_contract_probe as probe
from scripts.slurm.validate_qasper_contract_probe import validate_contract_probe


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self.text = json.dumps(payload, separators=(",", ":"))
        self.additional_kwargs = {"finish_reason": "stop"}


class _Provider:
    """A message/schema-driven provider double.

    The probe cases describe the input fixture, but they must not be a second
    implementation of the candidate/verifier state machine.  Every response
    below is derived from the messages passed to this callable and then
    projected onto the response schema supplied by production.
    """

    def __init__(self, *, reject_fault: bool = True) -> None:
        self.reject_fault = reject_fault
        self._candidate: str = ""

    def __call__(self, messages: object, **kwargs: object) -> _Response:
        response_format = kwargs.get("response_format")
        if not isinstance(response_format, dict):
            raise RuntimeError("provider response schema missing")
        schema = response_format.get("json_schema")
        if not isinstance(schema, dict):
            raise RuntimeError("provider response schema invalid")
        name = schema.get("name")
        if name == "qasper_typed_candidate":
            return self._candidate_response(messages, schema)
        if name == "semantic_evidence_set_proposition":
            return self._proposal(messages, schema)
        if name == "candidate_bound_unknown_audit":
            return self._unknown_audit(messages, schema)
        if name == "semantic_entailment_audit":
            return self._entailment_audit(messages, schema)
        raise AssertionError(f"unexpected production schema {name!r}")

    def _candidate_response(
        self, messages: object, schema: dict[str, object]
    ) -> _Response:
        text = _message_text(messages)
        marker = "CONTROLLED ORIGINAL CANDIDATE UNDER AUDIT:"
        if marker in text:
            candidate = _line_after_marker(text, marker, "controlled candidate")
        else:
            observation = _json_after_marker(
                text,
                "CANDIDATE EVIDENCE-SET OBSERVATION:",
                "candidate evidence observation",
            )
            selected_refs = observation.get("selected_refs")
            available_refs = _candidate_selector_refs(text)
            if not isinstance(selected_refs, list) or not selected_refs:
                raise RuntimeError("provider candidate evidence span missing")
            if not set(map(str, selected_refs)) <= available_refs:
                raise RuntimeError("provider candidate evidence ref missing")
            signal = str(observation.get("polarity_signal") or "").casefold()
            candidate = {
                "support": "yes",
                "explicit_contradiction": "no",
                "undetermined": "unanswerable",
            }.get(signal, "")
            if not candidate:
                raise RuntimeError("provider candidate evidence signal invalid")
        self._remember_candidate(candidate)
        properties = _schema_properties(schema)
        candidate_schema = properties.get("candidate")
        candidates = _schema_enum(candidate_schema)
        if candidates and candidate not in candidates:
            raise RuntimeError("provider candidate is outside response schema")
        return _Response({"candidate": candidate})

    def _proposal(self, messages: object, schema: dict[str, object]) -> _Response:
        text = _message_text(messages)
        candidate = _structured_candidate(text)
        self._remember_candidate(candidate)
        selector, evidence_text = _evidence_span(text)
        question = _question_from_message(text)
        signal = _evidence_signal(question, evidence_text)
        derived_judgment = _candidate_judgment(candidate, signal)
        controlled = _json_after_optional_marker(
            text,
            "CONTRACT PROBE CONTROLLED VERIFIER OUTPUT (NEGATIVE AUDITOR TEST):",
        )
        if controlled is not None:
            if not isinstance(controlled, dict):
                raise RuntimeError("controlled verifier proposal is not an object")
            proposal_judgment = str(controlled.get("candidate_judgment") or "")
            if proposal_judgment not in {"supported", "contradicted", "unknown"}:
                raise RuntimeError("controlled verifier proposal candidate mismatch")
            premises = controlled.get("premises")
            if not isinstance(premises, list) or not premises:
                raise RuntimeError("controlled verifier proposal premise missing")
            if str((premises[0] or {}).get("span_selector") or "") != selector:
                raise RuntimeError("controlled verifier proposal span mismatch")
            source = controlled
        else:
            source = {}
            proposal_judgment = derived_judgment
        return _Response(
            _proposal_payload(
                schema,
                proposal_judgment=proposal_judgment,
                candidate=candidate,
                selector=selector,
                evidence_text=evidence_text,
                signal=signal,
                source=source,
            )
        )

    def _entailment_audit(
        self, messages: object, schema: dict[str, object]
    ) -> _Response:
        text = _message_text(messages)
        proposal = _json_after_marker(
            text,
            "AUDIT THIS PROOF PROPOSAL:",
            "semantic audit proposal",
        )
        passed = _audit_entails_proposal(proposal)
        if not self.reject_fault:
            passed = True
        return _Response(_audit_payload(schema, proposal, passed=passed))

    def _unknown_audit(self, messages: object, schema: dict[str, object]) -> _Response:
        text = _message_text(messages)
        payload = _json_after_marker(
            text,
            "AUDIT THIS VERIFIER UNCERTAINTY:",
            "candidate unknown audit",
        )
        candidate = str(payload.get("original_candidate") or "").strip().casefold()
        if not candidate:
            raise RuntimeError("candidate unknown audit candidate missing")
        properties = _schema_properties(schema)
        candidate_schema = properties.get("audited_candidate")
        candidates = _schema_enum(candidate_schema)
        if candidates and candidate not in candidates:
            raise RuntimeError("candidate unknown audit candidate mismatch")
        reviewed = payload.get("audited_premises")
        passed = bool(candidate and isinstance(reviewed, list) and reviewed)
        values: dict[str, object] = {
            "audit_scope": payload.get(
                "audit_scope", "original_candidate_and_verifier_unknown_only"
            ),
            "audited_candidate": candidate,
            "audited_verdict": "insufficient_evidence",
            "audited_judgment": str(
                payload.get("verifier_judgment") or "unknown"
            ).casefold(),
            "typed_conclusion_present": passed,
            "reviewed_evidence_present": passed,
            "support_gap_valid": passed,
            "contradiction_gap_valid": passed,
            "relationship_consistent": passed,
            "replacement_candidate_allowed": False,
            "replacement_candidate": "",
        }
        return _Response(
            _schema_shape(
                values,
                _schema_properties(schema),
                _schema_required(schema),
                "candidate unknown audit",
            )
        )

    def _remember_candidate(self, candidate: str) -> None:
        candidate = str(candidate or "").strip().casefold()
        if candidate not in {"yes", "no", "unanswerable"}:
            raise RuntimeError("provider message candidate invalid")
        if self._candidate and self._candidate != candidate:
            raise RuntimeError(
                "provider observed candidate mismatch between message stacks"
            )
        self._candidate = candidate


def _message_text(messages: object) -> str:
    if not isinstance(messages, (list, tuple)) or not messages:
        raise RuntimeError("provider message stack missing")
    contents: list[str] = []
    for message in messages:
        content = (
            message.get("content")
            if isinstance(message, dict)
            else getattr(message, "content", None)
        )
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("provider message content missing")
        contents.append(content)
    return "\n\n".join(contents)


def _line_after_marker(text: str, marker: str, label: str) -> str:
    match = re.search(
        rf"{re.escape(marker)}\s*\n\s*([^\s\n]+)",
        text,
    )
    if not match:
        raise RuntimeError(f"provider {label} missing from message stack")
    return match.group(1).strip().casefold()


def _json_after_marker(text: str, marker: str, label: str) -> dict[str, Any]:
    value = _json_after_optional_marker(text, marker)
    if not isinstance(value, dict):
        raise RuntimeError(f"provider {label} missing or invalid")
    return value


def _json_after_optional_marker(text: str, marker: str) -> object | None:
    position = text.find(marker)
    if position < 0:
        return None
    remainder = text[position + len(marker) :].lstrip()
    try:
        value, _ = json.JSONDecoder().raw_decode(remainder)
    except json.JSONDecodeError as exc:
        raise RuntimeError("provider controlled JSON is invalid") from exc
    return value


def _structured_candidate(text: str) -> str:
    marker = "STRUCTURED CANDIDATE TO VERIFY:"
    return _line_after_marker(text, marker, "STRUCTURED CANDIDATE TO VERIFY")


def _evidence_span(text: str) -> tuple[str, str]:
    match = re.search(r"(?m)^\[(E\d+:S\d+)\]\s+([^\n]+)", text)
    if not match:
        raise RuntimeError("provider canonical evidence span missing")
    return match.group(1), match.group(2).strip()


def _question_from_message(text: str) -> str:
    match = re.search(r"(?m)^QUESTION:\s*\n([^\n]+)", text)
    if not match:
        raise RuntimeError("provider question missing from message stack")
    return match.group(1).strip()


def _candidate_judgment(candidate: str, signal: str) -> str:
    if signal == "undetermined" or candidate == "unanswerable":
        return "unknown"
    proposition_polarity = {
        "support": "yes",
        "explicit_contradiction": "no",
    }.get(signal)
    if proposition_polarity is None:
        raise RuntimeError("provider evidence polarity is invalid")
    return "supported" if candidate == proposition_polarity else "contradicted"


def _factory(*, case_id: str, **_: object) -> _Provider:
    del case_id
    return _Provider()


def _semantic_proposal_schema(candidate: str = "yes") -> dict[str, object]:
    from ktem.reasoning.mara_semantic_proposition_schema import (
        semantic_proposition_response_format,
    )

    return semantic_proposition_response_format(
        [],
        ["support:boolean_proposition"],
        candidate=candidate,
        applicable_proposition_slots=["actor", "predicate", "object"],
    )["json_schema"]


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
    audit_attempts = fail_event["transaction"]["audit"]["attempts"]
    assert audit_attempts
    verifier = auditor_fail["engine_terminal_evidence_bundle"]["metadata"][
        "semantic_proposition_verifier"
    ]
    assert verifier["audit_model_call_count"] >= 1
    assert verifier["candidate_verification_audit"]["status"] == "failed"
    assert auditor_fail["engine_terminal_answer"] == "unanswerable"
    assert auditor_fail["engine_terminal_commit"]["outcome"] == "safe_abstention"


def test_controlled_proposal_passes_exact_candidate_schema_and_parser() -> None:
    from ktem.reasoning.mara_semantic_contract_probe import (
        controlled_contract_probe_proposal,
    )
    from ktem.reasoning.mara_semantic_proposition_packing import (
        pack_semantic_proposition_evidence,
        required_semantic_proposition_slots,
    )

    from scripts.slurm.qasper_debug_contract_probe_cases import (
        _PROBE_CASES,
        _QUESTION,
        _build_request_and_bundle,
    )

    case = next(case for case in _PROBE_CASES if case.case_id == "auditor_fail")
    request, bundle = _build_request_and_bundle(case, 5)
    slots = required_semantic_proposition_slots(request)
    packing = pack_semantic_proposition_evidence(request, _QUESTION, slots, bundle)

    controlled = controlled_contract_probe_proposal(
        "base prompt",
        bundle=bundle,
        packing=packing,
        slots=slots,
        candidate="yes",
    )
    payload = _json_after_marker(
        controlled,
        "CONTRACT PROBE CONTROLLED VERIFIER OUTPUT (NEGATIVE AUDITOR TEST):",
        "controlled proposal",
    )

    assert "evidence_relation" not in payload
    assert "proof_mode" not in payload
    identity = bundle.metadata["contract_probe_controlled_proposal"][
        "payload_identity_gate"
    ]
    assert identity["status"] == "passed"
    assert identity["candidate"] == "yes"
    assert identity["schema_status"] == "accepted"
    assert identity["parser_status"] == "accepted"
    assert identity["payload_digest"]
    assert identity["candidate_schema_digest"]


def test_controlled_proposal_identity_gate_rejects_schema_mismatch() -> None:
    from ktem.reasoning.mara_semantic_contract_probe import (
        ControlledContractProbeIdentityError,
        controlled_contract_probe_proposal,
    )
    from ktem.reasoning.mara_semantic_proposition_packing import (
        pack_semantic_proposition_evidence,
        required_semantic_proposition_slots,
    )

    from scripts.slurm.qasper_debug_contract_probe_cases import (
        _PROBE_CASES,
        _QUESTION,
        _build_request_and_bundle,
    )

    case = next(case for case in _PROBE_CASES if case.case_id == "auditor_fail")
    request, bundle = _build_request_and_bundle(case, 5)
    control = bundle.metadata["contract_probe_controlled_proposal"]
    control["candidate_judgment"] = "unknown"
    slots = required_semantic_proposition_slots(request)
    packing = pack_semantic_proposition_evidence(request, _QUESTION, slots, bundle)

    with pytest.raises(
        ControlledContractProbeIdentityError,
        match="controlled_payload_schema_rejected",
    ):
        controlled_contract_probe_proposal(
            "base prompt",
            bundle=bundle,
            packing=packing,
            slots=slots,
            candidate="yes",
        )


def test_live_probe_uses_production_parser_and_auditor() -> None:
    rows = _run_probe(
        "http://provider.invalid/v1", "contract-probe-model", model_factory=_factory
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
            response_format = kwargs.get("response_format")
            response_format = (
                response_format if isinstance(response_format, dict) else {}
            )
            schema = response_format.get("json_schema")
            schema = schema if isinstance(schema, dict) else {}
            if schema.get("name") == "qasper_typed_candidate":
                return _Response({"candidate": "yes"})
            return value

    def factory(*, case_id: str, **kwargs: object) -> WrongProvider:
        del case_id, kwargs
        return WrongProvider()

    with pytest.raises(RuntimeError, match="provider observed|expected candidate"):
        _run_probe("http://provider.invalid/v1", "model", model_factory=factory)


def test_provider_rejects_missing_candidate_or_evidence_from_messages() -> None:
    provider = _Provider()
    schema = _semantic_proposal_schema()
    missing_candidate = [
        SimpleNamespace(
            content=(
                "QUESTION:\nDid the authors release the code for the evaluated system?\n\n"
                "CANONICAL EVIDENCE SPANS:\n[E1:S1] The authors released the code."
            )
        )
    ]
    with pytest.raises(RuntimeError, match="STRUCTURED CANDIDATE TO VERIFY"):
        provider(missing_candidate, response_format={"json_schema": schema})

    missing_evidence = [
        SimpleNamespace(
            content=(
                "QUESTION:\nDid the authors release the code for the evaluated system?\n\n"
                "STRUCTURED CANDIDATE TO VERIFY:\nyes"
            )
        )
    ]
    with pytest.raises(RuntimeError, match="canonical evidence span"):
        provider(missing_evidence, response_format={"json_schema": schema})


def test_provider_rejects_candidate_mismatch_between_message_stacks() -> None:
    provider = _Provider()
    from ktem.reasoning.mara_qasper_candidate import qasper_candidate_response_format

    provider(
        [SimpleNamespace(content="CONTROLLED ORIGINAL CANDIDATE UNDER AUDIT:\nyes")],
        response_format=qasper_candidate_response_format(),
    )
    messages = [
        SimpleNamespace(
            content=(
                "QUESTION:\nDid the authors release the code for the evaluated system?\n\n"
                "STRUCTURED CANDIDATE TO VERIFY:\nno\n\n"
                "CANONICAL EVIDENCE SPANS:\n[E1:S1] The authors did not release the code "
                "for the evaluated system."
            )
        )
    ]
    with pytest.raises(RuntimeError, match="candidate mismatch"):
        provider(
            messages, response_format={"json_schema": _semantic_proposal_schema("no")}
        )


def test_controlled_fault_requires_actual_auditor_rejection() -> None:
    def passing_fault_factory(*, case_id: str, **kwargs: object) -> _Provider:
        del case_id, kwargs
        return _Provider(reject_fault=False)

    with pytest.raises(RuntimeError, match="accepted semantic auditor rejection"):
        _run_probe(
            "http://provider.invalid/v1", "model", model_factory=passing_fault_factory
        )


def test_probe_write_replaces_artifact_without_duplicate_rows(tmp_path: Path) -> None:
    path = tmp_path / "contract_probe_predictions.jsonl"
    rows = [{"example_id": "one"}, {"example_id": "two"}]
    probe._write_rows(path, rows)
    probe._write_rows(path, rows)
    assert len(path.read_text(encoding="utf-8").splitlines()) == 2


def test_live_stage_probe_rows_pass_formal_provider_audit(tmp_path: Path) -> None:
    rows = _run_probe(
        "http://provider.invalid/v1", "contract-probe-model", model_factory=_factory
    )
    predictions = tmp_path / "contract_probe_predictions.jsonl"
    audit_path = tmp_path / "contract_probe_audit.json"
    probe._write_rows(predictions, rows)

    audit = validate_contract_probe(predictions, output_path=audit_path)

    assert audit["status"] == "passed"
    assert audit["failed_gates"] == []
    assert audit["behavior_violations"] == []
