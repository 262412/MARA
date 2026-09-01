from __future__ import annotations

import json
import re
from typing import Any

from benchmark.tests.qasper_contract_probe_auditor_support import (
    controlled_auditor_premise_texts,
)
from benchmark.tests.qasper_contract_probe_schema_support import (  # noqa: F401
    _proposal_schema_context,
    _schema_body,
    _schema_branch,
    _schema_enum,
    _schema_properties,
    _schema_proposition_scope,
    _schema_required,
    _schema_shape,
    _selector_premise_branch,
)

_AUDITOR_BASE_URL = "http://auditor.invalid/v1"
_AUDITOR_MODEL = "heterogeneous-auditor-model"


def _run_probe(
    base_url: str, model: str, *, model_factory: Any
) -> list[dict[str, Any]]:
    from scripts.slurm import qasper_debug_contract_probe as probe

    return probe.run_live_probes(
        base_url,
        model,
        auditor_base_url=_AUDITOR_BASE_URL,
        auditor_model=_AUDITOR_MODEL,
        model_factory=model_factory,
    )


def _assert_provider_call_and_span_evidence(
    rows: list[dict[str, Any]],
) -> None:
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
        lineage = verifier["semantic_data_lineage"]
        assert lineage["contract_id"] == "semantic_proposition_data_lineage.v1"
        assert lineage["proposal_contract"]["mode"] == "canonical_plan_selection"
        assert lineage["local_projection"]["status"] == "passed"
        assert lineage["proposal_attempts"][0]["raw_response_digest"]
        assert lineage["audit"]["attempts"][0]["raw_response_digest"]


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
    verifier = auditor_fail["engine_terminal_evidence_bundle"]["metadata"][
        "semantic_proposition_verifier"
    ]
    assert verifier["audit_model_call_count"] >= 1
    assert verifier["candidate_verification_audit"]["status"] == "failed"
    lineage = verifier["semantic_data_lineage"]
    assert lineage["status"] == "failed"
    assert lineage["first_inconsistency"] == {
        "stage": "auditor_semantics",
        "reason": "premise_fragment_not_entailed",
        "attempt": 1,
        "raw_response_digest": lineage["audit"]["attempts"][0]["raw_response_digest"],
    }
    assert verifier.get("proof_repair_count", 0) == 0
    assert verifier.get("recovery_transitions", []) == []
    assert auditor_fail["engine_terminal_answer"] == "unanswerable"
    assert auditor_fail["engine_terminal_commit"]["outcome"] == "safe_abstention"


def _normalize_text(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _candidate_selector_refs(text: str) -> set[str]:
    refs: set[str] = set()
    for serialized in re.findall(r"(?m)^selector_options=(\[[^\n]*\])$", text):
        try:
            options = json.loads(serialized)
        except json.JSONDecodeError as exc:
            raise RuntimeError("provider candidate selector JSON invalid") from exc
        for option in options if isinstance(options, list) else []:
            if isinstance(option, dict) and str(option.get("evidence_ref") or ""):
                refs.add(str(option["evidence_ref"]))
    return refs


def _evidence_signal(question: str, evidence_text: str) -> str:
    normalized = _normalize_text(evidence_text)
    if re.search(
        r"\b(?:does|do|did|doesn't|does not|do not|did not)\s+"
        r"(?:state|establish|indicate|show|confirm|specify)\b",
        normalized,
    ):
        return "undetermined"
    from ktem.reasoning.mara_qasper_candidate_selector_semantics import (
        candidate_polarity_signal,
    )

    return candidate_polarity_signal(question, evidence_text)


def _proposal_values(
    properties: dict[str, Any],
    premise_properties: dict[str, Any],
    source_premise: dict[str, Any],
    proposition_slots: list[str],
    support_slot_ids: list[str],
    applicable_slots: list[str],
    not_applicable_slots: list[str],
    *,
    proposal_judgment: str,
    candidate: str,
    selector: str,
    evidence_text: str,
    signal: str,
) -> dict[str, object]:
    del candidate
    relation = {
        "support": "proposition_support",
        "explicit_contradiction": "explicit_contradiction",
        "undetermined": "undetermined",
    }.get(signal, "")
    relation_schema = properties.get("evidence_relation")
    relation_enum = _schema_enum(relation_schema)
    if relation_enum and relation not in relation_enum:
        relation = relation_enum[0]
    source_fragment = str(source_premise.get("proposition_fragment") or "")
    fragment = source_fragment or evidence_text
    unresolved_slot_set = _unknown_unresolved_slot_set(
        properties,
        applicable_slots,
    )
    values: dict[str, object] = {
        "candidate_judgment": proposal_judgment,
        "evidence_relation": relation,
        "support_mode": "evidence_set",
        "proof_mode": "none" if proposal_judgment == "unknown" else "atomic_semantic",
        "jointly_complete": proposal_judgment != "unknown",
        "each_premise_required": proposal_judgment != "unknown",
        "premises": [],
        "not_applicable_proposition_slots": not_applicable_slots,
        "unknown_assessment": {
            "reviewed_span_selectors": [selector],
            "unresolved_proposition_slots": unresolved_slot_set,
            "support_gap": "The evidence does not establish the proposition.",
            "contradiction_gap": "The evidence does not explicitly contradict it.",
        },
    }
    if proposal_judgment != "unknown":
        premise_values: dict[str, object] = {
            "span_selector": selector,
            "proposition_fragment": fragment[:320],
            "supports_slot_ids": [
                value
                for value in source_premise.get("supports_slot_ids") or support_slot_ids
                if str(value) in support_slot_ids
            ],
            "binds_proposition_slots": [
                value
                for value in source_premise.get("binds_proposition_slots")
                or proposition_slots
                if str(value) in proposition_slots
            ],
        }
        if not premise_values["supports_slot_ids"] and support_slot_ids:
            premise_values["supports_slot_ids"] = [support_slot_ids[0]]
        if not premise_values["binds_proposition_slots"]:
            premise_values["binds_proposition_slots"] = list(proposition_slots)
        values["premises"] = [
            {
                key: value
                for key, value in premise_values.items()
                if key in premise_properties
            }
        ]
        values.pop("unknown_assessment", None)
    elif "premises" not in properties:
        values.pop("premises", None)
    return {key: value for key, value in values.items() if key in properties}


def _unknown_unresolved_slot_set(
    properties: dict[str, Any],
    proposition_slots: list[str],
) -> str:
    unknown_schema = properties.get("unknown_assessment")
    unknown_properties = (
        unknown_schema.get("properties") if isinstance(unknown_schema, dict) else {}
    )
    unknown_properties = (
        unknown_properties if isinstance(unknown_properties, dict) else {}
    )
    allowed = _schema_enum(unknown_properties.get("unresolved_proposition_slots"))
    selected = "|".join(proposition_slots)
    return selected if not allowed or selected in allowed else allowed[-1]


def _proposal_payload(
    schema: dict[str, object],
    *,
    proposal_judgment: str,
    candidate: str,
    selector: str,
    evidence_text: str,
    signal: str,
    source: dict[str, Any],
) -> dict[str, object]:
    branch = _schema_branch(schema, proposal_judgment)
    plan_properties = branch.get("properties")
    if isinstance(plan_properties, dict) and (
        "canonical_evidence_plan_id" in plan_properties
    ):
        plan_ids = [
            plan_id
            for plan_id in _schema_enum(
                plan_properties.get("canonical_evidence_plan_id")
            )
            if plan_id
        ]
        selected_plan_id = (
            ""
            if proposal_judgment == "unknown"
            else (plan_ids[0] if len(plan_ids) == 1 else "")
        )
        return _schema_shape(
            {
                "candidate_judgment": proposal_judgment,
                "canonical_evidence_plan_id": selected_plan_id,
            },
            plan_properties,
            {
                str(field)
                for field in branch.get("required") or []
                if isinstance(field, str)
            },
            "semantic plan selection",
        )
    (
        properties,
        required_fields,
        premise_properties,
        source_premise,
        proposition_slots,
        support_slot_ids,
        applicable_slots,
        not_applicable_slots,
    ) = _proposal_schema_context(
        schema,
        proposal_judgment,
        source,
        selector=selector,
    )
    values = _proposal_values(
        properties,
        premise_properties,
        source_premise,
        proposition_slots,
        support_slot_ids,
        applicable_slots,
        not_applicable_slots,
        proposal_judgment=proposal_judgment,
        candidate=candidate,
        selector=selector,
        evidence_text=evidence_text,
        signal=signal,
    )
    return _schema_shape(
        values,
        properties,
        required_fields,
        "semantic proposal",
    )


def _audit_entails_proposal(proposal: dict[str, Any]) -> bool:
    typed = proposal.get("typed_conclusion")
    question_proposition = proposal.get("question_proposition")
    premises = proposal.get("premises")
    if not isinstance(typed, dict) or not isinstance(question_proposition, dict):
        return False
    if not isinstance(premises, list) or not premises:
        return False
    polarity = str(typed.get("polarity") or "").casefold()
    question = str(question_proposition.get("surface") or "")
    object_surface = _normalize_text(question_proposition.get("object_surface"))
    if polarity not in {"yes", "no"} or not question or not object_surface:
        return False
    controlled_premises = controlled_auditor_premise_texts(proposal)
    if controlled_premises is None or len(controlled_premises) != len(premises):
        return False
    expected_signal = "support" if polarity == "yes" else "explicit_contradiction"
    for premise, (quote, fragment_text) in zip(premises, controlled_premises):
        if not isinstance(premise, dict):
            return False
        fragment = _normalize_text(fragment_text)
        normalized_quote = _normalize_text(quote)
        if normalized_quote.startswith(("if ", "unless ")):
            return False
        if not quote or not fragment or fragment not in _normalize_text(quote):
            return False
        if object_surface not in _normalize_text(quote):
            return False
        if _evidence_signal(question, quote) != expected_signal:
            return False
    return True


def _audit_premise_checks(
    properties: dict[str, Any],
    proposal: dict[str, Any],
    *,
    passed: bool,
) -> tuple[dict[str, Any], object]:
    premise_schema = properties.get("premise_checks")
    if isinstance(premise_schema, dict) and premise_schema.get("type") == "object":
        return _audit_premise_checks_object(properties, proposal, passed=passed)
    premise_properties: dict[str, Any] = {}
    premise_item = (
        premise_schema.get("items") if isinstance(premise_schema, dict) else {}
    )
    if isinstance(premise_item, dict):
        raw = premise_item.get("properties")
        premise_properties = raw if isinstance(raw, dict) else {}
    labels = _schema_enum(premise_properties.get("premise_ref"))
    premises = proposal.get("premises")
    premises = premises if isinstance(premises, list) else []
    if not labels:
        labels = [f"P{index}" for index in range(1, len(premises) + 1)]
    checks: list[dict[str, object]] = []
    for index, label in enumerate(labels):
        premise = (
            premises[index]
            if index < len(premises) and isinstance(premises[index], dict)
            else {}
        )
        source_slots = [
            str(value)
            for value in premise.get("binds_proposition_slots") or []
            if str(value)
        ]
        slot_schema = premise_properties.get("declared_proposition_slots", {})
        slot_items = slot_schema.get("items") if isinstance(slot_schema, dict) else {}
        allowed_slots = _schema_enum(slot_items)
        slots = [
            slot for slot in source_slots if not allowed_slots or slot in allowed_slots
        ]
        if (
            not slots
            and allowed_slots
            and "declared_proposition_slots" in premise_properties
        ):
            slots = list(allowed_slots[:1])
        quote = str(
            premise.get("quote") or premise.get("proposition_fragment") or "The"
        )
        values: dict[str, object] = {
            "premise_ref": label,
            "fragment_entailed": passed,
            "scope_consistent": passed,
            "proposition_bindings_valid": passed,
            "evidence_relation_valid": passed,
            "declared_proposition_slots": slots,
            "proposition_slot_checks": [
                {"slot": slot, "binding_valid": passed, "evidence_text": quote}
                for slot in slots
            ],
        }
        checks.append(
            _schema_shape(
                values,
                premise_properties,
                {
                    str(field)
                    for field in (
                        premise_item.get("required", [])
                        if isinstance(premise_item, dict)
                        else []
                    )
                    if isinstance(field, str)
                },
                "semantic audit premise",
            )
        )
    return premise_properties, checks


def _audit_premise_checks_object(
    properties: dict[str, Any],
    proposal: dict[str, Any],
    *,
    passed: bool,
) -> tuple[dict[str, Any], dict[str, dict[str, object]]]:
    premise_schema = properties.get("premise_checks")
    if not isinstance(premise_schema, dict):
        raise RuntimeError("provider semantic audit premise schema missing")
    premise_properties = premise_schema.get("properties")
    if not isinstance(premise_properties, dict):
        raise RuntimeError("provider semantic audit premise properties missing")
    labels = _audit_premise_labels(premise_schema, premise_properties)
    source_premises = proposal.get("premises")
    source_premises = source_premises if isinstance(source_premises, list) else []
    checks: dict[str, dict[str, object]] = {}
    for index, label in enumerate(labels):
        check_schema = premise_properties.get(label)
        if not isinstance(check_schema, dict):
            raise RuntimeError(f"provider semantic audit premise {label} missing")
        check_properties = check_schema.get("properties")
        check_properties = (
            check_properties if isinstance(check_properties, dict) else {}
        )
        required = {
            str(field)
            for field in check_schema.get("required", [])
            if isinstance(field, str)
        }
        premise = _source_premise(source_premises, index)
        values: dict[str, object] = {
            "fragment_entailed": passed,
            "scope_consistent": passed,
            "proposition_bindings_valid": passed,
            "evidence_relation_valid": passed,
            "proposition_slot_checks": _audit_slot_checks(
                check_properties,
                premise,
                label,
                passed=passed,
            ),
        }
        checks[label] = _schema_shape(
            values,
            check_properties,
            required,
            "semantic audit premise",
        )
    return premise_properties, checks


def _audit_premise_labels(
    premise_schema: dict[str, Any],
    premise_properties: dict[str, Any],
) -> list[str]:
    labels = [
        str(label)
        for label in premise_schema.get("required", [])
        if isinstance(label, str)
    ]
    return labels or [str(label) for label in premise_properties]


def _source_premise(
    premises: list[Any],
    index: int,
) -> dict[str, Any]:
    premise = premises[index] if index < len(premises) else {}
    return premise if isinstance(premise, dict) else {}


def _audit_slot_checks(
    check_properties: dict[str, Any],
    premise: dict[str, Any],
    label: str,
    *,
    passed: bool,
) -> dict[str, dict[str, object]]:
    slot_schema = check_properties.get("proposition_slot_checks")
    slot_properties = (
        slot_schema.get("properties") if isinstance(slot_schema, dict) else {}
    )
    slot_properties = slot_properties if isinstance(slot_properties, dict) else {}
    source_slots = {
        str(value)
        for value in premise.get("binds_proposition_slots") or []
        if str(value)
    }
    slots = [slot for slot in source_slots if slot in slot_properties]
    slots = slots or [str(slot) for slot in slot_properties]
    checks: dict[str, dict[str, object]] = {}
    for slot in slots:
        slot_spec = slot_properties.get(slot)
        slot_spec = slot_spec if isinstance(slot_spec, dict) else {}
        slot_spec_properties = slot_spec.get("properties")
        slot_spec_properties = (
            slot_spec_properties if isinstance(slot_spec_properties, dict) else {}
        )
        evidence_ref = _schema_enum(slot_spec_properties.get("evidence_ref"))
        if not evidence_ref:
            raise RuntimeError(
                f"provider semantic audit evidence ref schema missing: {label}:{slot}"
            )
        checks[slot] = {"binding_valid": passed, "evidence_ref": evidence_ref[0]}
    return checks


def _audit_conclusion(
    properties: dict[str, Any],
    *,
    passed: bool,
) -> dict[str, object]:
    conclusion_schema = properties.get("conclusion_check")
    conclusion_properties = (
        conclusion_schema.get("properties")
        if isinstance(conclusion_schema, dict)
        else {}
    )
    conclusion_properties = (
        conclusion_properties if isinstance(conclusion_properties, dict) else {}
    )
    raw_conclusion_required = (
        conclusion_schema.get("required") if isinstance(conclusion_schema, dict) else []
    )
    conclusion_required = (
        raw_conclusion_required if isinstance(raw_conclusion_required, list) else []
    )
    conclusion_values: dict[str, object] = {
        field: passed for field in conclusion_properties if field != "premise_ref"
    }
    return _schema_shape(
        conclusion_values,
        conclusion_properties,
        {str(field) for field in conclusion_required if isinstance(field, str)},
        "semantic audit conclusion",
    )


def _audit_payload(
    schema: dict[str, object], proposal: dict[str, Any], *, passed: bool
) -> dict[str, object]:
    properties = _schema_properties(schema)
    required_fields = _schema_required(schema)
    _, checks = _audit_premise_checks(properties, proposal, passed=passed)
    output_values = {
        "premise_checks": checks,
        "jointly_entails": passed,
        "each_premise_required": passed,
        "contradiction_free": passed,
        "conclusion_check": _audit_conclusion(properties, passed=passed),
    }
    return _schema_shape(
        output_values,
        properties,
        required_fields,
        "semantic audit",
    )


# Keep the existing provider-support import path stable while keeping the
# natural-quality fixture catalog in its own small module.
from benchmark.tests.qasper_contract_probe_natural_fixtures import (  # noqa: E402,F401
    NATURAL_QUALITY_PAYLOAD_FIXTURES,
    NaturalQualityPayloadFixture,
    natural_quality_payload_fixture,
)
