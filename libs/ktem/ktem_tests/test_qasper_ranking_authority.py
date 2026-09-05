from __future__ import annotations

from typing import Any

import pytest
from ktem.docqa.boolean_relations import boolean_relations_align
from ktem.docqa.polarity_contradiction_check import polarity_contradiction_check
from ktem.docqa.qasper_boolean_no_evidence import qasper_no_evidence_set_analysis
from ktem.docqa.question_proposition import (
    applicable_proposition_evidence_slots,
    build_question_proposition,
    resolve_question_proposition,
    typed_conclusion,
)
from ktem.docqa.semantic_relation_clause_validation import (
    semantic_relation_clause_analysis,
    semantic_required_argument_tokens,
)
from ktem.reasoning.mara_qasper_candidate_evidence import candidate_evidence_set_binding
from ktem.reasoning.mara_qasper_candidate_selector_semantics import (
    candidate_polarity_signal,
)
from ktem.reasoning.mara_qasper_semantic_pack import prepare_qasper_canonical_records

QUESTION = "Does BERT reach the best performance among all the algorithms compared?"
EVIDENCE = (
    "BERT-based model has not improved the scores obtained by neither NLNDE nor "
    "other baselines and is in second position."
)

RANKING_CONTRADICTION_EVIDENCE = (
    EVIDENCE,
    "BERT is ranked second among all the algorithms compared.",
)


def _selector(text: str) -> dict[str, Any]:
    return {
        "selector_id": "E1:S1",
        "text": text,
        "span_start": 0,
        "span_end": len(text),
    }


def test_best_performance_question_resolves_to_ranking_object() -> None:
    resolution = resolve_question_proposition(QUESTION)
    proposition = resolution.proposition

    assert resolution.status == "complete"
    assert proposition.actor == "BERT"
    assert proposition.subject_surface == "BERT"
    assert proposition.predicate == "rank"
    assert proposition.object_role == "ranking_target"
    assert proposition.object_type == "performance"
    assert proposition.object_surface == "best performance"
    assert proposition.quantifier == "all"
    assert proposition.relation_kind == "ranking"
    assert semantic_required_argument_tokens(QUESTION) == (
        "best",
        "performance",
    )


@pytest.mark.parametrize("evidence", RANKING_CONTRADICTION_EVIDENCE)
def test_non_winning_ranking_evidence_is_an_explicit_contradiction(
    evidence: str,
) -> None:
    semantics = qasper_no_evidence_set_analysis(QUESTION, [evidence])

    assert semantics["classification"] == "explicit_ranking_contradiction"
    assert semantics["reason"] == "explicit_non_winning_system_comparison"
    assert semantics["admissible_as_explicit_contradiction"] is True
    assert semantics["proposition_object"] == "best performance"
    assert boolean_relations_align(QUESTION, evidence) is True


def test_ranking_contradiction_binds_all_proposition_slots_in_one_clause() -> None:
    proposition = build_question_proposition(QUESTION)
    analysis = semantic_relation_clause_analysis(
        {
            "quote": EVIDENCE,
            "binds_proposition_slots": list(
                applicable_proposition_evidence_slots(proposition)
            ),
        },
        proposition,
    )

    assert analysis["status"] == "explicit_contradiction"
    assert analysis["joint_relation_clause_bound"] is True
    assert set(analysis["slot_evidence"]) == set(
        applicable_proposition_evidence_slots(proposition)
    )


@pytest.mark.parametrize("evidence", RANKING_CONTRADICTION_EVIDENCE)
def test_ranking_contradiction_binds_performance_without_literal_performance(
    evidence: str,
) -> None:
    proposition = build_question_proposition(QUESTION)
    analysis = semantic_relation_clause_analysis(
        {
            "quote": evidence,
            "binds_proposition_slots": list(
                applicable_proposition_evidence_slots(proposition)
            ),
        },
        proposition,
    )

    assert analysis["status"] == "explicit_contradiction"
    assert analysis["joint_relation_clause_bound"] is True
    assert set(analysis["required_object_tokens"]) == {"best", "performance"}
    assert set(analysis["covered_object_tokens"]) == {"best", "performance"}


@pytest.mark.parametrize("evidence", RANKING_CONTRADICTION_EVIDENCE)
def test_ranking_contradiction_survives_canonical_selector_projection(
    evidence: str,
) -> None:
    records = prepare_qasper_canonical_records(
        QUESTION,
        [{"evidence_id": "e1", "text": evidence, "selectors": [_selector(evidence)]}],
    )

    assert [
        selector["selector_id"]
        for record in records
        for selector in record["selectors"]
    ] == ["E1:S1"]
    binding = candidate_evidence_set_binding(records, QUESTION)
    assert binding["binding_state"] == "relation_bound_contradiction"
    assert binding["polarity_signal"] == "explicit_contradiction"


def test_ranking_contradiction_reverses_a_yes_candidate() -> None:
    proposition = build_question_proposition(QUESTION)
    check = polarity_contradiction_check(
        typed_conclusion(proposition, "yes"),
        [{"quote": EVIDENCE}],
    )

    assert check["status"] == "contradiction_detected"


def test_ranking_meta_mention_is_not_contradiction() -> None:
    meta = "The question asks whether BERT is ranked second among all algorithms."

    assert candidate_polarity_signal(QUESTION, meta) == "undetermined"
