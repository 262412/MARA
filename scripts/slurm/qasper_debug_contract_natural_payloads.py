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
        "none",
    ),
    NaturalQualityPayloadFixture(
        "proposer_slot_expectations_differ_from_verified_slot_evidence",
        "supported",
        "support",
        "none",
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
) -> dict[str, object]:
    del candidate
    branch = _schema_branch(schema, proposal_judgment)
    properties = _mapping(branch.get("properties"))
    required = _string_set(branch.get("required"))
    premise_properties, proposition_slots, support_slot_ids = _premise_context(
        properties
    )
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
        "not_applicable_proposition_slots": [
            slot
            for slot in ("actor", "predicate", "object", "quantifier")
            if slot not in proposition_slots
        ],
        "unknown_assessment": _unknown_assessment(
            properties,
            proposition_slots,
            selector,
        ),
    }
    if proposal_judgment != "unknown":
        if not proposition_slots:
            raise RuntimeError("natural-quality proposition slots missing")
        values["premises"] = [
            {
                key: value
                for key, value in {
                    "span_selector": selector,
                    "proposition_fragment": evidence_text[:320],
                    "supports_slot_ids": support_slot_ids[:1],
                    "binds_proposition_slots": proposition_slots,
                }.items()
                if key in premise_properties
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
) -> tuple[dict[str, Any], list[str], list[str]]:
    premise_schema = _mapping(properties.get("premises"))
    premise_item = _mapping(premise_schema.get("items"))
    premise_properties = _mapping(premise_item.get("properties"))
    binding_schema = _mapping(premise_properties.get("binds_proposition_slots"))
    proposition_slots = _enum(_mapping(binding_schema.get("items")))
    support_schema = _mapping(premise_properties.get("supports_slot_ids"))
    support_slot_ids = _enum(_mapping(support_schema.get("items")))
    return premise_properties, proposition_slots, support_slot_ids


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
