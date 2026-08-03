from __future__ import annotations

from ktem.docqa.boolean_proposition_evidence import (
    boolean_proposition_binding_trace,
    classify_boolean_evidence_candidates,
    classify_boolean_evidence_set,
)
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.query_planning import bind_evidence_slots, build_query_plan


def _item(evidence_id: str, text: str, *, section: str = "results") -> dict[str, str]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "section_id": section,
        "text": text,
    }


def test_relation_families_accept_claim_preserving_synonyms() -> None:
    cases = (
        ("Did the authors evaluate the system?", "We report results for the system."),
        (
            "Did the authors compare both systems?",
            "Our system outperforms the baseline.",
        ),
        ("Did the authors use external tools?", "We rely on external tools."),
        ("Did the authors train the model?", "We fine-tune the model."),
        ("Did the authors annotate the corpus?", "We construct labels for the corpus."),
    )

    for question, text in cases:
        trace = boolean_proposition_binding_trace(
            question, "yes", [_item("support", text)]
        )
        assert trace["final_support_evidence_ids"] == ["evidence:paper:support"]
        assert trace["normalized_relation"]


def test_actor_and_scope_mismatch_are_rejected_with_trace() -> None:
    related = _item(
        "related",
        "Smith et al. tested the model on clinical tasks.",
        section="related_work",
    )

    trace = boolean_proposition_binding_trace(
        "Did the authors evaluate the model on clinical tasks?",
        "yes",
        [related],
    )

    assert trace["final_support_evidence_ids"] == []
    assert trace["rejected_candidates"][0]["reason"] == (
        "cited_work_does_not_establish_current_paper_claim"
    )
    assert trace["rejected_candidates"][0]["actor_score"] == 0.0


def test_second_span_can_supply_answer_specific_support() -> None:
    item = _item(
        "mixed",
        "We did not train the model. We evaluated the model on clinical tasks.",
    )

    candidates = classify_boolean_evidence_candidates(
        "Did the authors evaluate the model on clinical tasks?",
        "yes",
        item,
    )
    trace = boolean_proposition_binding_trace(
        "Did the authors evaluate the model on clinical tasks?",
        "yes",
        [item],
    )

    assert len(candidates) == 2
    assert candidates[1].classification == "supports"
    assert trace["bound_support_span_ids"] == [candidates[1].span_id]


def test_one_item_preserves_opposite_polarity_span_candidates() -> None:
    item = _item(
        "conflict",
        (
            "We did not evaluate the model on clinical tasks. "
            "We evaluated the model on clinical tasks."
        ),
    )

    evidence_set = classify_boolean_evidence_set(
        "Did the authors evaluate the model on clinical tasks?",
        "yes",
        [item],
    )

    assert len(evidence_set.supports) == 1
    assert len(evidence_set.contradicts) == 1
    assert evidence_set.supports[0].span_id != evidence_set.contradicts[0].span_id


def test_query_plan_binding_is_polarity_neutral_then_answer_specific() -> None:
    question = "Did the authors evaluate the model on clinical tasks?"
    negative = _item(
        "negative",
        "We did not evaluate the model on clinical tasks.",
    )
    plan = build_query_plan(
        question,
        answer_type="boolean",
        verification_domain="qasper",
    )

    bound = bind_evidence_slots(plan, [negative])
    trace = boolean_proposition_binding_trace(question, "no", [negative])

    [slot] = bound.evidence_slots
    assert slot.status == "retrieved_unverified"
    assert slot.evidence_ids == (identity_of(negative).key,)
    assert trace["final_support_evidence_ids"] == [identity_of(negative).key]
    assert trace["final_contradiction_evidence_ids"] == []


def test_selected_but_unbound_boolean_candidate_stays_missing() -> None:
    question = "Did the authors evaluate the model on clinical tasks?"
    unrelated = _item("unrelated", "We released the source code.")
    plan = build_query_plan(
        question,
        answer_type="boolean",
        verification_domain="qasper",
    )

    bound = bind_evidence_slots(plan, [unrelated])

    [slot] = bound.evidence_slots
    assert slot.status == "missing"
    assert slot.evidence_ids == ()


def test_zero_explicit_support_fails_closed() -> None:
    trace = boolean_proposition_binding_trace(
        "Did the authors evaluate the model on clinical tasks?",
        "yes",
        [_item("unrelated", "The paper introduces a model architecture.")],
    )

    assert trace["final_support_evidence_ids"] == []
    assert trace["binding_status"] == "missing"
