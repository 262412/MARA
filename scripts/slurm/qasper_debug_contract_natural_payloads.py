from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NaturalQualityPayloadFixture:
    """One controlled mutation derived from a natural pre-audit failure."""

    fixture_id: str
    proposal_judgment: str
    signal: str
    mutation: str


NATURAL_QUALITY_PAYLOAD_FIXTURES: tuple[NaturalQualityPayloadFixture, ...] = (
    NaturalQualityPayloadFixture(
        "proposer_over_declares_actor_quantifier",
        "supported",
        "support",
        "append_quantifier_to_bindings",
    ),
    NaturalQualityPayloadFixture(
        "title_only_span_binds_relation_object",
        "supported",
        "support",
        "replace_bindings_with_applicable_slots",
    ),
    NaturalQualityPayloadFixture(
        "proposer_slot_expectations_differ_from_verified_slot_evidence",
        "supported",
        "support",
        "replace_bindings_with_applicable_slots",
    ),
    NaturalQualityPayloadFixture(
        "unknown_assessment_duplicate_unresolved_slots",
        "unknown",
        "undetermined",
        "duplicate_unknown_slots",
    ),
)

_FIXTURES = {
    fixture.fixture_id: fixture for fixture in NATURAL_QUALITY_PAYLOAD_FIXTURES
}


def natural_quality_payload_fixture(
    fixture_id: str,
    schema: dict[str, object],
    *,
    candidate: str,
    selector: str,
    evidence_text: str,
    support_slot_ids: list[str],
) -> dict[str, object]:
    """Build a schema-shaped payload and apply exactly one controlled defect."""

    try:
        fixture = _FIXTURES[fixture_id]
    except KeyError as exc:
        raise ValueError(
            f"unknown natural-quality payload fixture: {fixture_id}"
        ) from exc
    payload = _proposal_payload(
        schema,
        proposal_judgment=fixture.proposal_judgment,
        candidate=candidate,
        selector=selector,
        evidence_text=evidence_text,
        signal=fixture.signal,
        support_slot_ids=support_slot_ids,
    )
    if fixture.mutation == "append_quantifier_to_bindings":
        premise = _first_premise(payload)
        bindings = premise.get("binds_proposition_slots")
        if not isinstance(bindings, list):
            raise RuntimeError("natural-quality proposal bindings missing")
        premise["binds_proposition_slots"] = [*bindings, "quantifier"]
    elif fixture.mutation == "duplicate_unknown_slots":
        assessment = payload.get("unknown_assessment")
        if not isinstance(assessment, dict):
            raise RuntimeError("natural-quality unknown assessment missing")
        unresolved = str(assessment.get("unresolved_proposition_slots") or "")
        if not unresolved:
            raise RuntimeError("natural-quality unresolved slots missing")
        first = unresolved.split("|", maxsplit=1)[0]
        assessment["unresolved_proposition_slots"] = f"{first}|{first}"
    elif fixture.mutation == "replace_bindings_with_applicable_slots":
        premise = _first_premise(payload)
        body_properties = _mapping(_mapping(schema.get("schema")).get("properties"))
        properties = (
            body_properties
            if "canonical_evidence_plan_id" in body_properties
            else _mapping(
                _schema_branch(schema, fixture.proposal_judgment).get("properties")
            )
        )
        applicable_slots = (
            ["actor", "predicate", "object"]
            if "canonical_evidence_plan_id" in properties
            else _schema_proposition_scope(properties)[0]
        )
        premise["binds_proposition_slots"] = applicable_slots
    elif fixture.mutation != "none":
        raise RuntimeError(
            f"unsupported natural-quality payload mutation: {fixture.mutation}"
        )
    return deepcopy(payload)


def _first_premise(payload: dict[str, object]) -> dict[str, Any]:
    premises = payload.get("premises")
    if not isinstance(premises, list) or not premises:
        raise RuntimeError("natural-quality proposal premise missing")
    premise = premises[0]
    if not isinstance(premise, dict):
        raise RuntimeError("natural-quality proposal premise invalid")
    return premise


def _proposal_payload(
    schema: dict[str, object],
    *,
    proposal_judgment: str,
    candidate: str,
    selector: str,
    evidence_text: str,
    signal: str,
    support_slot_ids: list[str],
) -> dict[str, object]:
    del candidate
    body_properties = _mapping(_mapping(schema.get("schema")).get("properties"))
    if "canonical_evidence_plan_id" in body_properties:
        return _expanded_model_payload(
            proposal_judgment=proposal_judgment,
            selector=selector,
            evidence_text=evidence_text,
            signal=signal,
            support_slot_ids=support_slot_ids,
        )
    return _legacy_proposal_payload(
        schema,
        proposal_judgment=proposal_judgment,
        selector=selector,
        evidence_text=evidence_text,
        signal=signal,
        support_slot_ids=support_slot_ids,
    )


def _legacy_proposal_payload(
    schema: dict[str, object],
    *,
    proposal_judgment: str,
    selector: str,
    evidence_text: str,
    signal: str,
    support_slot_ids: list[str],
) -> dict[str, object]:
    branch = _schema_branch(schema, proposal_judgment)
    properties = _mapping(branch.get("properties"))
    required = _string_set(branch.get("required"))
    (premise_properties, selector_slots, schema_support_slot_ids,) = _premise_context(
        properties,
        selector=selector,
    )
    proposition_slots, not_applicable_slots = _schema_proposition_scope(properties)
    selected_support_slot_ids = schema_support_slot_ids or support_slot_ids
    relation = {
        "support": "proposition_support",
        "explicit_contradiction": "explicit_contradiction",
        "undetermined": "undetermined",
    }.get(signal, "")
    relation_values = _enum(properties.get("evidence_relation"))
    if relation_values and relation not in relation_values:
        relation = relation_values[0]
    values: dict[str, object] = {
        "candidate_judgment": proposal_judgment,
        "evidence_relation": relation,
        "support_mode": "evidence_set",
        "proof_mode": "none" if proposal_judgment == "unknown" else "atomic_semantic",
        "jointly_complete": proposal_judgment != "unknown",
        "each_premise_required": proposal_judgment != "unknown",
        "premises": [],
        "not_applicable_proposition_slots": not_applicable_slots,
        "unknown_assessment": _unknown_assessment(
            properties,
            proposition_slots,
            selector,
        ),
    }
    if proposal_judgment != "unknown":
        premise_fields = premise_properties or {
            "span_selector": {},
            "proposition_fragment": {},
            "supports_slot_ids": {},
            "binds_proposition_slots": {},
        }
        values["premises"] = [
            {
                key: value
                for key, value in {
                    "span_selector": selector,
                    "proposition_fragment": evidence_text[:320],
                    "supports_slot_ids": selected_support_slot_ids[:1],
                    "binds_proposition_slots": selector_slots or proposition_slots,
                }.items()
                if key in premise_fields
            }
        ]
        values.pop("unknown_assessment", None)
    elif "premises" not in properties:
        values.pop("premises", None)
    payload = {key: value for key, value in values.items() if key in properties}
    missing = required - set(payload)
    if missing:
        raise RuntimeError(
            f"natural-quality proposal schema fields missing: {sorted(missing)}"
        )
    return payload


def _expanded_model_payload(
    *,
    proposal_judgment: str,
    selector: str,
    evidence_text: str,
    signal: str,
    support_slot_ids: list[str],
) -> dict[str, object]:
    payload: dict[str, object] = {
        "candidate_judgment": proposal_judgment,
        "support_mode": "evidence_set",
        "jointly_complete": proposal_judgment != "unknown",
        "each_premise_required": proposal_judgment != "unknown",
        "premises": [],
        "not_applicable_proposition_slots": ["quantifier"],
    }
    if proposal_judgment == "unknown":
        payload["unknown_assessment"] = {
            "reviewed_span_selectors": [selector],
            "unresolved_proposition_slots": "actor|predicate|object",
            "support_gap": "The evidence does not establish the proposition.",
            "contradiction_gap": ("The evidence does not explicitly contradict it."),
        }
        return payload
    payload["premises"] = [
        {
            "span_selector": selector,
            "proposition_fragment": evidence_text[:320],
            "supports_slot_ids": support_slot_ids[:1],
            "binds_proposition_slots": ["actor", "predicate", "object"],
        }
    ]
    if signal == "explicit_contradiction":
        payload["evidence_relation"] = "explicit_contradiction"
    return payload


def _schema_branch(schema: dict[str, object], judgment: str) -> dict[str, Any]:
    body = _mapping(schema.get("schema"))
    branches = body.get("oneOf")
    if not isinstance(branches, list):
        return body
    for branch in branches:
        branch = branch if isinstance(branch, dict) else {}
        properties = _mapping(branch.get("properties"))
        if judgment in _enum(properties.get("candidate_judgment")):
            return branch
    raise RuntimeError("natural-quality judgment is outside proposal schema")


def _premise_context(
    properties: dict[str, Any],
    *,
    selector: str,
) -> tuple[dict[str, Any], list[str], list[str]]:
    premise_schema = _mapping(properties.get("premises"))
    premise_item = _mapping(premise_schema.get("items"))
    premise_item = _selector_premise_branch(premise_item, selector=selector)
    premise_properties = _mapping(premise_item.get("properties"))
    binding_schema = _mapping(premise_properties.get("binds_proposition_slots"))
    binding_values = binding_schema.get("enum")
    if (
        isinstance(binding_values, list)
        and len(binding_values) == 1
        and isinstance(binding_values[0], list)
    ):
        proposition_slots = [str(value) for value in binding_values[0]]
    else:
        proposition_slots = _enum(_mapping(binding_schema.get("items")))
    support_schema = _mapping(premise_properties.get("supports_slot_ids"))
    support_slot_ids = _enum(_mapping(support_schema.get("items")))
    return premise_properties, proposition_slots, support_slot_ids


def _selector_premise_branch(
    premise_item: dict[str, Any],
    *,
    selector: str,
) -> dict[str, Any]:
    branches = premise_item.get("oneOf")
    if not isinstance(branches, list):
        return premise_item
    for raw_branch in branches:
        branch = _mapping(raw_branch)
        properties = _mapping(branch.get("properties"))
        if selector in _enum(properties.get("span_selector")):
            return branch
    raise RuntimeError("natural-quality selector is outside proposal schema")


def _schema_proposition_scope(
    properties: dict[str, Any],
) -> tuple[list[str], list[str]]:
    all_slots = ("actor", "predicate", "object", "quantifier")
    not_applicable_schema = _mapping(properties.get("not_applicable_proposition_slots"))
    values = not_applicable_schema.get("enum")
    if (
        not isinstance(values, list)
        or len(values) != 1
        or not isinstance(values[0], list)
    ):
        raise RuntimeError("natural-quality proposition scope missing")
    not_applicable = [str(value) for value in values[0]]
    return (
        [slot for slot in all_slots if slot not in not_applicable],
        not_applicable,
    )


def _unknown_assessment(
    properties: dict[str, Any],
    proposition_slots: list[str],
    selector: str,
) -> dict[str, object]:
    schema = _mapping(properties.get("unknown_assessment"))
    assessment_properties = _mapping(schema.get("properties"))
    allowed = _enum(assessment_properties.get("unresolved_proposition_slots"))
    unresolved = "|".join(proposition_slots)
    if allowed and unresolved not in allowed:
        unresolved = allowed[-1]
    return {
        "reviewed_span_selectors": [selector],
        "unresolved_proposition_slots": unresolved,
        "support_gap": "The evidence does not establish the proposition.",
        "contradiction_gap": "The evidence does not explicitly contradict it.",
    }


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _enum(value: object) -> list[str]:
    enum = value.get("enum") if isinstance(value, dict) else None
    return [str(item) for item in enum] if isinstance(enum, list) else []


def _string_set(value: object) -> set[str]:
    return {str(item) for item in value} if isinstance(value, list) else set()
