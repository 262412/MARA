from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

import pytest
from jsonschema import Draft202012Validator, ValidationError
from ktem.docqa.question_proposition import (
    applicable_proposition_evidence_slots,
    build_question_proposition,
    proposition_evidence_bindings,
    typed_conclusion,
)
from ktem.docqa.semantic_entailment_audit import (
    semantic_entailment_audit_attestation,
    semantic_entailment_audit_validation_reason,
)
from ktem.reasoning.mara_semantic_entailment_audit import (
    parse_semantic_entailment_audit,
    semantic_entailment_audit_response_format,
)


def _atomic_audit(
    *,
    slots: tuple[str, ...] = ("actor", "predicate", "object", "quantifier"),
    evidence: dict[str, str] | None = None,
) -> dict:
    evidence = evidence or {
        "actor": "The authors",
        "predicate": "compared",
        "object": "two systems",
        "quantifier": "two",
    }
    return {
        "premise_checks": [
            {
                "premise_ref": "P1",
                "fragment_entailed": True,
                "scope_consistent": True,
                "proposition_bindings_valid": True,
                "evidence_relation_valid": True,
                "declared_proposition_slots": list(slots),
                "proposition_slot_checks": [
                    {
                        "slot": slot,
                        "binding_valid": True,
                        "evidence_text": evidence[slot],
                    }
                    for slot in slots
                ],
            }
        ],
        "jointly_entails": True,
        "each_premise_required": True,
        "contradiction_free": True,
        "conclusion_check": {
            "conclusion_entailed": True,
            "actor_consistent": True,
            "predicate_consistent": True,
            "object_consistent": True,
            "polarity_consistent": True,
            "quantifier_consistent": True,
            "scope_consistent": True,
        },
    }


def _premise_audit_reason(quote: str) -> str:
    question = "Did the authors compare the two systems?"
    proposition = build_question_proposition(question)
    applicable_slots = applicable_proposition_evidence_slots(proposition)
    canonical_bindings = proposition_evidence_bindings(proposition)
    premise = {
        "evidence_id": "evidence-1",
        "quote": quote,
        "span_start": 0,
        "span_end": len(quote),
        "proposition_fragment": quote,
        "supports_slot_ids": ["support:boolean_proposition"],
        "binds_proposition_slots": list(applicable_slots),
        "proposition_slot_bindings": {
            slot: canonical_bindings[slot] for slot in applicable_slots
        },
        "evidence_relation": "proposition_support",
    }
    audit_result = _atomic_audit(
        slots=applicable_slots,
        evidence={
            "actor": "The authors",
            "predicate": "compared",
            "object": "two systems",
            "quantifier": "two",
        },
    )
    attestation = semantic_entailment_audit_attestation(
        question,
        "yes",
        [premise],
        model="independent-test-auditor",
        seed=18,
        proof_mode="atomic_semantic",
        proposition=proposition,
        conclusion=typed_conclusion(proposition, "yes"),
        auditor_relationship="distinct_model",
        audit_result=audit_result,
    )
    return semantic_entailment_audit_validation_reason(
        question,
        "yes",
        [premise],
        attestation,
        proof_mode="atomic_semantic",
        proposition=proposition,
        conclusion=typed_conclusion(proposition, "yes"),
        release_mode=False,
    )


def test_semantic_auditor_rejects_a_binding_absent_from_its_exact_quote() -> None:
    assert (
        _premise_audit_reason("The authors compared another dataset.")
        == "semantic_entailment_proposition_binding_unbound"
    )


def test_semantic_auditor_accepts_all_applicable_slots_in_one_exact_span() -> None:
    assert _premise_audit_reason("The authors compared the two systems.") == ""


@pytest.mark.parametrize(
    "quote",
    (
        "## Comparison",
        "the two systems",
        "The proposed model compares the two systems.",
    ),
)
def test_semantic_auditor_rejects_non_proof_spans(quote: str) -> None:
    assert _premise_audit_reason(quote) == "semantic_entailment_premise_quote_not_proof"


def test_audit_parser_rejects_an_uncontrolled_slot_evidence_ref() -> None:
    payload: dict[str, Any] = {
        **_atomic_audit(),
        "premise_checks": {
            "P1": {
                "fragment_entailed": True,
                "scope_consistent": True,
                "evidence_relation_valid": True,
                "proposition_slot_checks": {
                    "actor": {
                        "binding_valid": True,
                        "evidence_ref": "P1:actor",
                    },
                    "predicate": {
                        "binding_valid": True,
                        "evidence_ref": "P1:predicate",
                    },
                },
            }
        },
    }
    expected = {
        "P1": {
            "actor": "The authors compared the systems.",
            "predicate": "The authors compared the systems.",
        }
    }
    parsed = parse_semantic_entailment_audit(
        json.dumps(payload),
        premise_labels=["P1"],
        premise_slot_expectations={"P1": ("actor", "predicate")},
        premise_slot_evidence=expected,
    )
    assert parsed.value is not None

    payload["premise_checks"]["P1"]["proposition_slot_checks"]["predicate"][
        "evidence_ref"
    ] = "free-form evidence"
    parsed = parse_semantic_entailment_audit(
        json.dumps(payload),
        premise_labels=["P1"],
        premise_slot_expectations={"P1": ("actor", "predicate")},
        premise_slot_evidence=expected,
    )
    assert parsed.value is None
    assert parsed.failure_reason == "premise_check_slot_evidence_invalid"


def test_auditor_schema_controls_slot_refs_and_parser_projects_exact_text() -> None:
    expected = {
        "P1": {
            "actor": "The authors compared the systems.",
            "predicate": "The authors compared the systems.",
        }
    }
    response_format = semantic_entailment_audit_response_format(
        ["P1"],
        premise_slot_expectations={"P1": ("actor", "predicate")},
        premise_slot_evidence=expected,
    )
    schema = response_format["json_schema"]["schema"]
    payload: dict[str, Any] = {
        "premise_checks": {
            "P1": {
                "fragment_entailed": False,
                "scope_consistent": False,
                "evidence_relation_valid": False,
                "proposition_slot_checks": {
                    "actor": {
                        "binding_valid": True,
                        "evidence_ref": "P1:actor",
                    },
                    "predicate": {
                        "binding_valid": False,
                        "evidence_ref": "P1:predicate",
                    },
                },
            }
        },
        "jointly_entails": False,
        "each_premise_required": False,
        "contradiction_free": True,
        "conclusion_check": {
            "conclusion_entailed": False,
            "actor_consistent": True,
            "predicate_consistent": False,
            "object_consistent": False,
            "polarity_consistent": True,
            "quantifier_consistent": True,
            "scope_consistent": False,
        },
    }

    Draft202012Validator(schema).validate(payload)
    parsed = parse_semantic_entailment_audit(
        json.dumps(payload),
        premise_labels=["P1"],
        premise_slot_expectations={"P1": ("actor", "predicate")},
        premise_slot_evidence=expected,
    )

    assert parsed.failure_reason == ""
    assert parsed.value is not None
    checks = parsed.value["premise_checks"][0]
    assert checks["declared_proposition_slots"] == ["actor", "predicate"]
    assert checks["proposition_bindings_valid"] is False
    assert checks["proposition_slot_checks"] == [
        {
            "slot": "actor",
            "binding_valid": True,
            "evidence_text": "The authors compared the systems.",
        },
        {
            "slot": "predicate",
            "binding_valid": False,
            "evidence_text": "The authors compared the systems.",
        },
    ]

    invalid = deepcopy(payload)
    invalid["premise_checks"]["P1"]["proposition_slot_checks"]["predicate"][
        "evidence_ref"
    ] = "free-form evidence"
    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(invalid)
