from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from typing import Any

import pytest
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.qasper_boolean_no_evidence import qasper_no_evidence_set_analysis
from ktem.docqa.question_proposition import build_question_proposition
from ktem.docqa.semantic_relation_clause_validation import (
    semantic_relation_evidence_set_constraint,
)
from ktem.reasoning.mara_qasper_candidate_evidence import (
    candidate_evidence_set_binding,
    candidate_required_slots_from_binding,
)
from ktem.reasoning.mara_qasper_semantic_pack import (
    freeze_qasper_canonical_semantic_pack,
    prepare_qasper_canonical_records,
)
from ktem.reasoning.mara_semantic_proposition_packing import (
    pack_semantic_proposition_evidence,
    required_semantic_proposition_slots,
)
from ktem.reasoning.mara_semantic_proposition_span_selectors import (
    canonical_span_selectors,
)

QUESTION = "Did the authors compare the two systems?"


def _selector(selector_id: str, text: str, start: int = 0) -> dict[str, Any]:
    return {
        "selector_id": selector_id,
        "text": text,
        "span_start": start,
        "span_end": start + len(text),
    }


def _request(question: str) -> SimpleNamespace:
    return SimpleNamespace(
        origin="benchmark",
        verification_domain="qasper",
        dataset_family="qasper",
        answer_type="boolean",
        question=question,
        query=question,
        query_plan={
            "answer_type": "boolean",
            "evidence_slots": [
                {
                    "slot_id": "support:boolean_proposition",
                    "description": "complete proposition support",
                    "required_for_verification": True,
                    "evidence_ids": [],
                    "evidence_refs": [],
                }
            ],
        },
    )


def test_stored_selector_authority_is_recomputed_for_current_proposition() -> None:
    text = "The paper discusses the two systems."
    selector = {
        **_selector("E1:S1", text),
        "allowed_proposition_slots": ["actor", "predicate", "object", "quantifier"],
        "relation_bearing": True,
        "candidate_relation_role": "polarity_evidence",
        "local_relation_state": "affirmative_assertion",
    }
    binding = candidate_evidence_set_binding(
        [{"evidence_id": "e1", "text": text, "selectors": [selector]}],
        QUESTION,
    )

    assert binding["binding_status"] == "missing"
    assert binding["support"] is False
    assert binding["explicit_contradiction"] is False
    assert binding["evidence_refs"] == []


def test_canonical_selector_records_exact_child_span_identity_per_slot() -> None:
    text = "The authors compared the two systems"
    canonical = prepare_qasper_canonical_records(
        QUESTION,
        [
            {
                "evidence_id": "e1",
                "text": text,
                "selectors": [_selector("E1:S1", text)],
            }
        ],
    )

    [selector] = canonical[0]["selectors"]
    child_spans = selector["proposition_slot_spans"]
    assert set(child_spans) == {"actor", "predicate", "object", "quantifier"}
    for slot, child in child_spans.items():
        start = child["span_start"] - selector["span_start"]
        end = child["span_end"] - selector["span_start"]
        assert selector["text"][start:end] == child["text"]
        assert child["parent_selector_id"] == selector["selector_id"]
        assert child["parent_span_start"] == selector["span_start"]
        assert child["parent_span_end"] == selector["span_end"]
        assert child["text_digest"]
        assert child["parent_text_digest"]
        assert slot in selector["allowed_proposition_slots"]


def test_selector_universe_discards_generic_affirmative_sentence() -> None:
    question = "Are the automatically constructed datasets subject to quality control?"
    generic = "The automatically constructed datasets enable controlled experiments."
    contradiction = (
        "The automatically constructed datasets were not subject to quality control."
    )
    canonical = prepare_qasper_canonical_records(
        question,
        [
            {
                "evidence_id": "generic",
                "text": generic,
                "selectors": [_selector("E1:S1", generic)],
            },
            {
                "evidence_id": "contradiction",
                "text": contradiction,
                "selectors": [_selector("E2:S1", contradiction)],
            },
        ],
    )

    refs = {
        selector["selector_id"]
        for record in canonical
        for selector in record["selectors"]
    }
    assert refs == {"E2:S1"}
    binding = candidate_evidence_set_binding(canonical, question)
    assert binding["polarity_signal"] == "explicit_contradiction"


def test_candidate_required_slots_are_a_projection_of_one_binding() -> None:
    text = "The authors compared the two systems"
    records = [
        {
            "evidence_id": "e1",
            "text": text,
            "selectors": [_selector("E1:S1", text)],
        }
    ]
    canonical = prepare_qasper_canonical_records(QUESTION, records)
    binding = candidate_evidence_set_binding(canonical, QUESTION)
    slots = candidate_required_slots_from_binding(
        [
            {
                "slot_id": "support:boolean_proposition",
                "description": "complete proposition support",
            }
        ],
        binding,
    )

    [slot] = slots
    assert slot["binding_status"] == binding["binding_status"] == "bound"
    assert slot["evidence_ids"] == binding["evidence_ids"]
    assert slot["evidence_refs"] == binding["evidence_refs"]
    assert slot["proposition_slot_evidence_refs"] == binding["slot_evidence_refs"]
    assert slot["proposition_binding_digest"] == binding["binding_digest"]


def test_pack_freeze_rejects_observation_required_slot_divergence() -> None:
    question = QUESTION
    request = _request(question)
    bundle = EvidenceBundle(
        route="doc_text",
        items=[
            {
                "evidence_id": "chunk-1",
                "source_id": "paper",
                "text": "The authors compared the two systems.",
            }
        ],
    )
    base_slots = required_semantic_proposition_slots(request)
    source = pack_semantic_proposition_evidence(
        request,
        question,
        base_slots,
        bundle,
        candidate_priority=True,
    )
    records = prepare_qasper_canonical_records(question, source.records)
    binding = candidate_evidence_set_binding(records, question)
    projected = candidate_required_slots_from_binding(base_slots, binding)
    inconsistent = deepcopy(projected)
    inconsistent[0]["evidence_refs"] = []

    with pytest.raises(
        ValueError, match="canonical_semantic_pack_binding_inconsistent"
    ):
        freeze_qasper_canonical_semantic_pack(
            bundle,
            question=question,
            slots=base_slots,
            source_packing=source,
            records=records,
            candidate_transaction_id="candidate-transaction-1",
            candidate_binding=binding,
            candidate_required_slots=inconsistent,
        )


@pytest.mark.parametrize(
    ("question", "spans", "classification"),
    [
        (
            "Did the authors collect the two datasets?",
            ["The authors did not collect the two datasets."],
            "explicit_negation",
        ),
        (
            "Did the authors collect the two datasets?",
            [
                "We evaluated two datasets: Alpha and Beta.",
                "We collected Alpha, while Beta came from an existing external source.",
            ],
            "role_incompatibility",
        ),
        (
            "Are the automatically constructed datasets subject to quality control?",
            [
                "It is difficult to validate the generated datasets at scale.",
                "Only initial samples were validated; full studies remain future work.",
            ],
            "partial_scope_only",
        ),
        (
            "Is car-speak language a collection of abstract features that the "
            "classifier is later trained on?",
            [
                "Car-speak is abstract language about physical vehicle attributes.",
                "The classifiers are trained on review vectors.",
            ],
            "role_incompatibility",
        ),
    ],
)
def test_qasper_no_semantics_accepts_only_auditable_contradiction_classes(
    question: str,
    spans: list[str],
    classification: str,
) -> None:
    result = qasper_no_evidence_set_analysis(question, spans)

    assert result["classification"] == classification
    assert result["admissible_as_explicit_contradiction"] is True
    assert result["closed_world_inference_required"] is False


def test_qasper_no_semantics_marks_omission_as_annotation_contract_gap() -> None:
    result = qasper_no_evidence_set_analysis(
        "Did the authors collect the two datasets?",
        ["We evaluated two datasets in the experiments."],
    )

    assert result["classification"] == "absence_only"
    assert result["admissible_as_explicit_contradiction"] is False
    assert result["closed_world_inference_required"] is True
    assert result["annotation_contract_status"] == "ambiguous_no_evidence_semantics"


def test_role_incompatibility_uses_the_same_local_verifier_contract() -> None:
    question = "Did the authors collect the two datasets?"
    result = semantic_relation_evidence_set_constraint(
        [
            {
                "quote": "We evaluated two datasets: Alpha and Beta.",
                "binds_proposition_slots": ["actor", "object", "quantifier"],
            },
            {
                "quote": (
                    "We collected Alpha, while Beta came from an existing "
                    "external source."
                ),
                "binds_proposition_slots": ["actor", "predicate"],
            },
        ],
        build_question_proposition(question),
        "no",
        auditor_relationship="distinct_model",
    )

    assert result["status"] == "passed"
    assert result["reason"] == ""
    assert result["qasper_no_evidence_semantics"]["classification"] == (
        "role_incompatibility"
    )


@pytest.mark.parametrize(
    (
        "question",
        "paragraphs",
        "expected_binding_state",
        "expected_structural_features",
    ),
    [
        (
            "Did they collected the two datasets?",
            [
                "We tested the proposed model on two different datasets: "
                "FBFans and CreateDebate. FBFans is a privately-owned dataset, "
                "and CreateDebate is a public dataset.",
                "The CreateDebate dataset was collected from an English online "
                "debate forum.",
            ],
            "unresolved",
            {"cross_span", "quantifier", "entity_alias"},
        ),
        (
            "Do they add one latent variable for each language pair in their "
            "Bayesian model?",
            [
                "We make copies of the monolingual model for each language and "
                "add additional crosslingual latent variables to couple the models."
            ],
            "unresolved",
            {"quantifier", "entity_alias"},
        ),
        (
            "Does this method help in sentiment classification task improvement?",
            [
                "Consistent with previous findings, cwrs offer large improvements "
                "across all tasks. This holds for phrase-structure parsing. Overall, "
                "shallow syntax is not particularly helpful when using cwrs."
            ],
            "unresolved",
            {"cross_span", "paraphrase", "entity_alias"},
        ),
        (
            "Do they inspect their model to see if their model learned to associate "
            "image parts with words related to entities?",
            [
                "Error Analysis shows example cases where visual contexts affect "
                "prediction of named entities. The model links image regions with "
                "entity-related words."
            ],
            "relation_bound_support",
            {"cross_span", "paraphrase", "entity_alias"},
        ),
        (
            "Is car-speak language collection of abstract features that classifier "
            "is later trained on?",
            [
                "Car-speak is abstract language that pertains to a car's physical "
                "attributes.",
                "We train three classifiers on the review vectors that we prepared.",
            ],
            "unresolved",
            {"cross_span", "paraphrase", "entity_alias"},
        ),
        (
            "Are the automatically constructed datasets subject to quality control?",
            [
                "The automatically constructed datasets come from knowledge resources.",
                "It is much harder to validate the quality control of such data at scale. "
                "Initial experiments validate only samples of our data.",
            ],
            "unresolved",
            {"cross_span", "paraphrase"},
        ),
    ],
)
def test_natural_qasper_structures_share_one_bounded_selector_universe(
    question: str,
    paragraphs: list[str],
    expected_binding_state: str,
    expected_structural_features: set[str],
) -> None:
    records = [
        {
            "label": f"E{index}",
            "evidence_id": f"evidence-{index}",
            "text": text,
            "text_start": 0,
            "selectors": canonical_span_selectors(
                f"E{index}",
                text,
                0,
                None,
                selector_max_chars=640,
            ),
        }
        for index, text in enumerate(paragraphs, start=1)
    ]
    canonical = prepare_qasper_canonical_records(question, records)
    binding = candidate_evidence_set_binding(canonical, question)

    assert binding["binding_state"] == expected_binding_state
    if expected_binding_state == "unresolved":
        assert binding["binding_status"] == "missing"
        assert binding["evidence_refs"] == []
    else:
        assert binding["binding_status"] == "bound"
        assert set(binding["required_slots"]) <= set(binding["covered_slots"])
        assert expected_structural_features <= set(binding["structural_features"])
    assert 1 <= len(binding["selector_universe_refs"]) <= 16
    assert sum(len(record["selectors"]) for record in canonical) <= 16
