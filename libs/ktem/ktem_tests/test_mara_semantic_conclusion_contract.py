from __future__ import annotations

from ktem.docqa.conclusion_audit import (
    ConclusionAudit,
    conclusion_audit_attestation,
    conclusion_audit_validation_reason,
)
from ktem.docqa.question_proposition import (
    QuestionProposition,
    build_question_proposition,
    typed_conclusion,
)

QUESTION = "Did the authors compare cross-lingual and single-language evaluation?"


def _audit(relationship: str) -> tuple[object, dict]:
    proposition = build_question_proposition(QUESTION)
    conclusion = typed_conclusion(proposition, "yes")
    audit = conclusion_audit_attestation(
        conclusion,
        {
            "conclusion_entailed": True,
            "polarity_consistent": True,
            "quantifier_consistent": True,
            "scope_consistent": True,
        },
        auditor_relationship=relationship,
        model="independent-test-auditor",
        seed=8,
    )
    return conclusion, audit


def test_typed_question_proposition_and_conclusion_audit_bind_by_digest() -> None:
    proposition = build_question_proposition(QUESTION)
    conclusion, audit = _audit("distinct_model")

    assert isinstance(proposition, QuestionProposition)
    assert proposition.as_dict()["proposition_id"] == proposition.proposition_id
    assert conclusion.proposition_id == proposition.proposition_id
    typed_audit = ConclusionAudit(
        conclusion_id=audit["conclusion_id"],
        conclusion_entailed=audit["conclusion_entailed"],
        polarity_consistent=audit["polarity_consistent"],
        quantifier_consistent=audit["quantifier_consistent"],
        scope_consistent=audit["scope_consistent"],
        auditor_relationship=audit["auditor_relationship"],
        model=audit["model"],
        seed=audit["seed"],
    )
    assert isinstance(typed_audit, ConclusionAudit)
    assert conclusion_audit_validation_reason(
        audit, conclusion, release_mode=True
    ) == ""


def test_release_mode_rejects_same_instance_conclusion_auditor() -> None:
    conclusion, audit = _audit("same_instance")

    assert conclusion_audit_validation_reason(
        audit, conclusion, release_mode=True
    ) == "release_conclusion_auditor_not_independent"
