from __future__ import annotations

import pytest
from ktem.docqa.question_proposition import (
    applicable_proposition_evidence_slots,
    build_question_proposition,
)
from ktem.docqa.semantic_relation_clause_validation import (
    locally_allowed_proposition_slots,
    semantic_relation_clause_analysis,
    semantic_relation_evidence_set_constraint,
)
from ktem.reasoning.mara_qasper_candidate_selector_semantics import (
    candidate_polarity_signal,
    revalidated_selector_semantics,
)


def _analysis(question: str, evidence: str) -> dict[str, object]:
    proposition = build_question_proposition(question)
    return semantic_relation_clause_analysis(
        {
            "quote": evidence,
            "binds_proposition_slots": list(
                applicable_proposition_evidence_slots(proposition)
            ),
        },
        proposition,
    )


@pytest.mark.parametrize(
    ("question", "statement"),
    (
        (
            "Did the authors release the code for the evaluated system?",
            "The authors released the code for the evaluated system.",
        ),
        (
            "Did the authors compare the two systems?",
            "The authors compared the two systems.",
        ),
        (
            "Did the authors evaluate the model on clinical tasks?",
            "The authors evaluated the model on clinical tasks.",
        ),
        (
            "Did the authors inspect their model?",
            (
                "The authors inspected their model to determine whether visual "
                "contexts affected predictions."
            ),
        ),
        (
            "Did the authors inspect their model?",
            (
                "The authors inspected their model to determine if visual "
                "contexts affected predictions."
            ),
        ),
    ),
)
def test_asserted_events_remain_eligible_for_support(
    question: str,
    statement: str,
) -> None:
    proposition = build_question_proposition(question)
    applicable = applicable_proposition_evidence_slots(proposition)
    analysis = _analysis(question, statement)

    assert analysis["assertion_scope"] == "asserted"
    assert analysis["status"] == "affirmative_assertion"
    assert analysis["joint_relation_clause_bound"] is True
    assert locally_allowed_proposition_slots(statement, proposition) == applicable
    assert candidate_polarity_signal(question, statement) == "support"


@pytest.mark.parametrize(
    ("question", "conditional", "expected_scope"),
    (
        (
            "Did the authors release the code for the evaluated system?",
            (
                "If the authors released the code for the evaluated system, "
                "reproducibility would improve."
            ),
            "conditional",
        ),
        (
            "Did the authors compare the two systems?",
            (
                "Unless the authors compared the two systems, the evaluation "
                "would remain incomplete."
            ),
            "conditional",
        ),
        (
            "Did the authors compare the two systems?",
            (
                "Suppose the authors compared the two systems; the evaluation "
                "would then be more useful."
            ),
            "hypothetical",
        ),
        (
            "Did the authors evaluate the model on clinical tasks?",
            "The authors might evaluate the model on clinical tasks.",
            "hypothetical",
        ),
        (
            "Did the authors release the code for the evaluated system?",
            (
                "Whether the authors released the code for the evaluated system "
                "remains unclear."
            ),
            "hypothetical",
        ),
        (
            "Did the authors evaluate the model on clinical tasks?",
            (
                "Had the authors evaluated the model on clinical tasks, the "
                "results would have been stronger."
            ),
            "conditional",
        ),
        (
            "Did the authors release the code for the evaluated system?",
            (
                "The authors released the code for the evaluated system if "
                "the artifact review passed."
            ),
            "conditional",
        ),
    ),
)
def test_conditional_and_hypothetical_relations_are_not_support_events(
    question: str,
    conditional: str,
    expected_scope: str,
) -> None:
    proposition = build_question_proposition(question)
    analysis = _analysis(question, conditional)
    selector = {
        "selector_id": "E1:S1",
        "evidence_id": "evidence-1",
        "event_id": "event-1",
        "span_start": 0,
        "span_end": len(conditional),
        "text": conditional,
    }
    semantics = revalidated_selector_semantics(selector, question, conditional)
    constraint = semantic_relation_evidence_set_constraint(
        [
            {
                "quote": conditional,
                "event_id": "event-1",
                "binds_proposition_slots": list(
                    applicable_proposition_evidence_slots(proposition)
                ),
            }
        ],
        proposition,
        "yes",
        auditor_relationship="distinct_model",
    )

    assert analysis["assertion_scope"] == expected_scope
    assert analysis["target_relation_present"] is True
    assert analysis["status"] == "unbound"
    assert analysis["evidence_relation"] == "undetermined"
    assert analysis["joint_relation_clause_bound"] is False
    assert locally_allowed_proposition_slots(conditional, proposition) == ()
    assert semantics["slots"] == []
    assert semantics["candidate_relation_role"] == "uncertainty_context"
    assert semantics["local_relation_state"] == "unbound"
    assert semantics["polarity_signal"] == "undetermined"
    assert candidate_polarity_signal(question, conditional) == "undetermined"
    assert constraint["status"] == "rejected"
    assert constraint["reason"] == "local_semantic_relation_unasserted_scope"
