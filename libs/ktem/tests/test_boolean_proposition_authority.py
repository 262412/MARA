from __future__ import annotations

from ktem.docqa.boolean_authoritative_conflict import (
    authority_atom_key,
    authority_sides_are_disjoint,
    conflict_sides_are_complete,
)
from ktem.docqa.boolean_claim_verification import boolean_claim_authority
from ktem.docqa.boolean_proposition_evidence import classify_boolean_evidence_candidates


def _item(
    text: str,
    *,
    span_id: str = "span",
    page_label: str = "1",
    section_id: str = "results",
) -> dict[str, object]:
    return {
        "source_id": "synthetic-paper",
        "span_id": span_id,
        "page_label": page_label,
        "section_id": section_id,
        "text": text,
    }


def test_exact_proposition_does_not_inject_question_object_into_authority():
    question = "Overall, did the authors experiment on other tasks?"
    item = _item(
        "For our experiments, we use BioBERT, an adaptation of BERT for the "
        "biomedical domain."
    )

    authority = boolean_claim_authority(question, "yes", [item])

    assert authority is not None
    assert authority.status == "unknown"
    assert not authority.supporting
    assessments = classify_boolean_evidence_candidates(question, "yes", item)
    assert all(value.classification != "supports" for value in assessments)


def test_qualifier_and_aggregate_scope_change_boolean_polarity():
    question = (
        "Overall, does having parallel data improve semantic role induction "
        "across multiple languages?"
    )
    item = _item(
        "Adding word alignments in parallel sentences results in small, non "
        "significant improvements in semantic role induction across multiple "
        "languages, even if there is some labeled data available in the source "
        "language."
    )

    authority = boolean_claim_authority(question, "yes", [item])

    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "no"
    assert authority.semantic_correction_applied is True
    assert len(authority.supporting) == 1
    evidence = authority.supporting[0]
    assert evidence.polarity == "no"
    assert evidence.qualifier == "non_significant"
    assert evidence.relation == "improve"
    assert evidence.object
    assert "parallel" in evidence.object
    assert evidence.quote == item["text"]
    assert evidence.evidence_id.startswith("span:synthetic-paper:")
    assert evidence.evidence_ref == evidence.span_id


def test_exact_relation_span_keeps_negative_polarity_and_does_not_merge_neighbor():
    question = "Does the method improve robustness?"
    item = _item("The method improves accuracy, but does not improve robustness.")

    assessments = classify_boolean_evidence_candidates(question, "yes", item)
    negative = [value for value in assessments if value.classification == "contradicts"]

    assert len(negative) == 1
    assert negative[0].proposition.polarity == "no"
    assert "robustness" in negative[0].span_text.lower()
    assert "accuracy" not in negative[0].span_text.lower()


def test_explicit_negative_relation_supports_canonical_no():
    question = "Did the authors evaluate the baseline?"
    item = _item("The study reports that the baseline was not evaluated.")

    authority = boolean_claim_authority(question, "yes", [item])

    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "no"
    assert authority.supporting[0].polarity == "no"
    assert authority.supporting[0].relation == "evaluate"
    assert authority.supporting[0].object == "baseline"


def test_closed_world_negative_without_explicit_or_exhaustive_evidence_abstains():
    question = "Did the authors evaluate the baseline?"
    item = _item("The study presents a new model and reports its results.")

    authority = boolean_claim_authority(question, "no", [item])

    assert authority is not None
    assert authority.status == "unknown"
    assert authority.canonical_answer_polarity == ""
    assert not authority.supporting
    assert not authority.contradicting


def test_all_quantifier_requires_every_named_argument_in_exact_span():
    question = "Did the authors evaluate all datasets A and B?"
    incomplete = _item("We evaluated dataset A.", section_id="experiments")
    complete = _item(
        "We evaluated all datasets A and B.",
        span_id="complete",
        section_id="experiments",
    )

    incomplete_authority = boolean_claim_authority(question, "yes", [incomplete])
    complete_authority = boolean_claim_authority(question, "yes", [complete])

    assert incomplete_authority is not None
    assert incomplete_authority.status == "unknown"
    assert complete_authority is not None
    assert complete_authority.status == "supported"
    assert complete_authority.supporting[0].quantifier == "all"


def test_existential_some_quantifier_is_recorded_in_authority():
    question = "Did the authors evaluate some datasets?"
    item = _item("We evaluated dataset A.", section_id="experiments")

    authority = boolean_claim_authority(question, "yes", [item])

    assert authority is not None
    assert authority.status == "supported"
    assert authority.supporting[0].quantifier == "some"


def test_authoritative_conflict_retains_disjoint_exact_identity_and_quote():
    question = "Does the method improve robustness?"
    positive = _item("The method improves robustness.", span_id="positive")
    negative = _item("The method does not improve robustness.", span_id="negative")

    authority = boolean_claim_authority(question, "yes", [positive, negative])

    assert authority is not None
    assert authority.status == "conflicting"
    conflict = authority.authoritative_conflict
    assert conflict is not None
    assert conflict_sides_are_complete(conflict)
    positives = conflict["positive_authorities"]
    negatives = conflict["negative_authorities"]
    assert authority_sides_are_disjoint(positives, negatives)
    assert authority_atom_key(positives[0]) != authority_atom_key(negatives[0])
    assert positives[0]["evidence_ref"] == positives[0]["span_id"]
    assert negatives[0]["evidence_ref"] == negatives[0]["span_id"]
    assert positives[0]["quote"] == positive["text"]
    assert negatives[0]["quote"] == negative["text"]


def test_conflict_authority_rejects_mismatched_quote_or_span_reference():
    authority = {
        "evidence_id": "span:synthetic-paper:positive",
        "evidence_ref": "span:synthetic-paper:positive#quote:0:30",
        "span_id": "span:synthetic-paper:positive#quote:0:30",
        "quote": "The method improves robustness.",
        "span_start": 0,
        "span_end": 30,
        "actor": "current_paper",
        "section_scope": "results",
        "relation": "improve",
        "object": "robustness",
        "quantifier": "none",
        "qualifier": "none",
        "polarity": "yes",
        "source_id": "synthetic-paper",
        "page_label": "1",
    }
    mismatched = dict(authority, evidence_ref="wrong-ref")

    assert not conflict_sides_are_complete(
        {
            "contract_id": "boolean_authoritative_conflict.v1",
            "positive_authorities": [mismatched],
            "negative_authorities": [dict(authority, polarity="no")],
            "status": "verified_conflict",
        }
    )
