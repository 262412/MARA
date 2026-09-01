from __future__ import annotations

from ktem.reasoning.mara_semantic_local_consistency import (
    deterministic_local_premise_consistency,
)


def _audit(*, semantic_fields_valid: bool) -> dict[str, object]:
    return {
        "premise_checks": [
            {
                "premise_ref": "P1",
                "fragment_entailed": False,
                "scope_consistent": semantic_fields_valid,
                "proposition_bindings_valid": semantic_fields_valid,
                "evidence_relation_valid": semantic_fields_valid,
                "proposition_slot_checks": [
                    {
                        "slot": "predicate",
                        "binding_valid": semantic_fields_valid,
                    }
                ],
            }
        ],
        "jointly_entails": semantic_fields_valid,
        "each_premise_required": semantic_fields_valid,
        "contradiction_free": semantic_fields_valid,
        "conclusion_check": {
            "conclusion_entailed": semantic_fields_valid,
            "actor_consistent": semantic_fields_valid,
            "predicate_consistent": semantic_fields_valid,
            "object_consistent": semantic_fields_valid,
            "polarity_consistent": semantic_fields_valid,
            "quantifier_consistent": semantic_fields_valid,
            "scope_consistent": semantic_fields_valid,
        },
    }


def _premises() -> list[dict[str, str]]:
    return [
        {
            "quote": "The authors released the code.",
            "proposition_fragment": "authors released the code",
        }
    ]


def test_exact_fragment_can_identify_only_a_literal_auditor_disagreement() -> None:
    consistency = deterministic_local_premise_consistency(
        _premises(),
        _audit(semantic_fields_valid=True),
    )

    assert consistency["status"] == "auditor_internal_inconsistency"
    assert consistency["disagreement_scope"] == "literal_fragment_only"
    assert consistency["override_eligible"] is True
    assert consistency["semantic_denial_fields"] == []
    assert consistency["inconsistent_premise_refs"] == ["P1"]


def test_exact_fragment_cannot_erase_an_auditor_semantic_denial() -> None:
    consistency = deterministic_local_premise_consistency(
        _premises(),
        _audit(semantic_fields_valid=False),
    )

    assert consistency["status"] == "auditor_semantic_rejection"
    assert consistency["disagreement_scope"] == "semantic"
    assert consistency["override_eligible"] is False
    assert consistency["inconsistent_premise_refs"] == []
    assert "P1.scope_consistent" in consistency["semantic_denial_fields"]
    assert "P1.evidence_relation_valid" in consistency["semantic_denial_fields"]
    assert "jointly_entails" in consistency["semantic_denial_fields"]
    assert (
        "conclusion_check.conclusion_entailed" in consistency["semantic_denial_fields"]
    )
