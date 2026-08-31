from __future__ import annotations

from typing import Any

from ktem.docqa.question_proposition import build_question_proposition
from ktem.docqa.semantic_relation_clause_validation import (
    semantic_relation_clause_analysis,
)
from ktem.reasoning.mara_qasper_candidate_evidence import candidate_evidence_set_binding
from ktem.reasoning.mara_qasper_semantic_pack import prepare_qasper_canonical_records
from ktem.reasoning.mara_semantic_proposition_span_selectors import (
    canonical_span_selectors,
)


def _sentence_records(text: str) -> list[dict[str, Any]]:
    return [
        {
            "label": "E1",
            "evidence_id": "evidence-1",
            "text": text,
            "text_start": 0,
            "selectors": canonical_span_selectors(
                "E1",
                text,
                0,
                None,
                selector_max_chars=640,
            ),
        }
    ]


def test_local_semantic_alignment_builds_one_complete_paragraph_event_plan() -> None:
    question = (
        "Do they add one latent variable for each language pair in their "
        "Bayesian model?"
    )
    text = (
        "We make copies of the monolingual model for each language and add "
        "additional crosslingual latent variables to couple the monolingual "
        "models. Concretely, whenever aligned arguments correspond, we add a "
        "CLV as a parent of the two corresponding role variables."
    )

    canonical = prepare_qasper_canonical_records(question, _sentence_records(text))
    binding = candidate_evidence_set_binding(canonical, question)

    assert binding["binding_state"] == "relation_bound_support"
    support = binding["canonical_evidence_plan"]["support_plan"]
    assert len(support["event_subplans"]) == 1
    assert support["required_object_tokens"] == [
        "each",
        "language",
        "latent",
        "model",
        "one",
        "pair",
        "variable",
    ]
    alignments = [
        selector["semantic_alignment"]
        for record in canonical
        for selector in record["selectors"]
        if selector.get("semantic_alignment")
    ]
    assert alignments
    assert any("one" in value["semantic_matches"] for value in alignments)
    for alignment in alignments:
        for matches in alignment["semantic_matches"].values():
            for match in matches:
                start = match["span_start"]
                end = match["span_end"]
                assert text[start:end] == match["text"]

    second = next(
        selector
        for record in canonical
        for selector in record["selectors"]
        if "a CLV as a parent" in selector["text"]
    )
    premise = {
        "evidence_id": second["evidence_id"],
        "span_selector": second["selector_id"],
        "quote": second["text"],
        "span_start": second["span_start"],
        "span_end": second["span_end"],
        "binds_proposition_slots": second["allowed_proposition_slots"],
        "event_id": second["event_id"],
        "local_relation_state": second["local_relation_state"],
        "predicate_match_kind": second["predicate_match_kind"],
        "semantic_alignment": second["semantic_alignment"],
        "proposition_slot_spans": second["proposition_slot_spans"],
    }
    analysis = semantic_relation_clause_analysis(
        premise,
        build_question_proposition(question),
    )
    assert analysis["slot_evidence"]["object"]["text"] == (
        "a CLV as a parent of the two corresponding role variables"
    )


def test_object_companion_semantics_remain_local_to_analysis_event() -> None:
    question = (
        "Do they inspect their model to see if their model learned to associate "
        "image parts with words related to entities?"
    )
    text = (
        "Error Analysis: Table 4 shows cases where visual contexts affect "
        "prediction of named entities. Visual contexts provide similarities to "
        "the token semantics from training examples, and the model predicts the "
        "token as a named entity."
    )

    canonical = prepare_qasper_canonical_records(question, _sentence_records(text))
    binding = candidate_evidence_set_binding(canonical, question)

    assert binding["binding_state"] == "relation_bound_support"
    support = binding["canonical_evidence_plan"]["support_plan"]
    assert len(support["event_subplans"]) == 1
    selected = {
        selector["selector_id"]: selector
        for record in canonical
        for selector in record["selectors"]
        if selector["selector_id"] in support["span_refs"]
    }
    assert {selector["event_id"] for selector in selected.values()} == {
        support["event_subplans"][0]["event_id"]
    }
    companion = next(
        selector
        for selector in selected.values()
        if "predicate" not in selector["allowed_proposition_slots"]
    )
    assert companion["local_relation_state"] == "unbound"
    assert companion["semantic_alignment"]["polarity_relation"] == "undetermined"
    assert "word" in set(companion["object_tokens"])
    assert "learn" not in set(companion["object_tokens"])


def test_frozen_selector_universe_retains_multiple_proposition_spans() -> None:
    question = "Did the authors compare the two systems?"
    text = (
        "The authors compared the two systems in the primary experiment.\n\n"
        "The authors compared the two systems again in the ablation study."
    )

    canonical = prepare_qasper_canonical_records(question, _sentence_records(text))
    binding = candidate_evidence_set_binding(canonical, question)
    selector_refs = [
        selector["selector_id"]
        for record in canonical
        for selector in record["selectors"]
    ]

    assert selector_refs == ["E1:S1", "E1:S2"]
    assert binding["selector_universe_refs"] == selector_refs
    assert binding["plan_construction_trace"]["bounded_selector_refs"] == selector_refs
    assert (
        binding["plan_construction_trace"]["valid_candidate_refs"][
            "proposition_support"
        ]
        == selector_refs
    )
