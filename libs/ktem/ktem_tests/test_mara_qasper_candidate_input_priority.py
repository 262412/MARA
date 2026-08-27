from __future__ import annotations

from types import SimpleNamespace

from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.reasoning.mara_qasper_candidate_evidence import (
    candidate_evidence_set_binding,
    candidate_selector_options,
)
from ktem.reasoning.mara_qasper_candidate_prompt import _candidate_prompt
from ktem.reasoning.mara_semantic_candidate_priority import candidate_record_slot_hints
from ktem.reasoning.mara_semantic_proposition_packing import (
    pack_semantic_proposition_evidence,
)


def _selector(selector_id: str, text: str, start: int) -> dict[str, object]:
    return {
        "selector_id": selector_id,
        "text": text,
        "span_start": start,
        "span_end": start + len(text),
    }


def test_record_slot_hints_preserve_quantifier_counterevidence() -> None:
    hints = candidate_record_slot_hints(
        "Did the authors collect the two datasets?",
        "We evaluated two datasets, but only CreateDebate was collected by us.",
    )

    assert set(hints) == {"actor", "object", "quantifier"}
    assert "predicate" not in hints


def test_candidate_packing_prioritizes_relation_and_quantifier_over_record_id() -> None:
    question = "Did the authors collect the two datasets?"
    preferred_id = "evidence:paper:preferred"
    request = SimpleNamespace(
        query_plan={
            "evidence_slots": [
                {
                    "required_for_verification": True,
                    "slot_id": "support:boolean_proposition",
                    "evidence_ids": [preferred_id],
                }
            ]
        }
    )
    bundle = EvidenceBundle(
        route="text_rag",
        items=[
            {
                "evidence_id": "preferred",
                "source_id": "paper",
                "text": "The paper discusses the experimental setting.",
            },
            {
                "evidence_id": "quantified",
                "source_id": "paper",
                "text": "We evaluated two datasets in the experiments.",
            },
            {
                "evidence_id": "relation",
                "source_id": "paper",
                "text": "The CreateDebate dataset was collected from a forum.",
            },
        ],
    )

    verifier_packing = pack_semantic_proposition_evidence(
        request,
        question,
        [{"slot_id": "support:boolean_proposition", "description": "support"}],
        bundle,
    )
    candidate_packing = pack_semantic_proposition_evidence(
        request,
        question,
        [{"slot_id": "support:boolean_proposition", "description": "support"}],
        bundle,
        candidate_priority=True,
    )

    assert verifier_packing.records[0]["evidence_id"] == preferred_id
    assert [record["evidence_id"] for record in candidate_packing.records[:2]] == [
        "evidence:paper:relation",
        "evidence:paper:quantified",
    ]


def test_candidate_selector_options_put_relation_spans_before_titles() -> None:
    question = (
        "Is car-speak language a collection of abstract features that the classifier "
        "is trained on?"
    )
    title = "# Car-speak features"
    definition = "Car-speak is abstract language about a car's physical attributes."
    training = "We train classifiers on review vectors, not on car-speak features."
    text = f"{title}\n{definition}\n{training}"
    definition_start = len(title) + 1
    training_start = definition_start + len(definition) + 1
    record = {
        "evidence_id": "evidence:paper:car-speak",
        "text": text,
        "selectors": [
            _selector("E1:S1", title, 0),
            _selector("E1:S2", definition, definition_start),
            _selector("E1:S3", training, training_start),
        ],
    }

    options = candidate_selector_options(record, question=question)

    assert options[0]["evidence_ref"] in {"E1:S2", "E1:S3"}
    assert options[-1]["evidence_ref"] == "E1:S1"


def test_composite_candidate_evidence_does_not_infer_cross_span_polarity() -> None:
    question = "Did the authors collect the two datasets?"
    quantified = "We tested the proposed method on two different datasets."
    relation = "The CreateDebate dataset was collected from a forum."
    records = [
        {
            "evidence_id": "evidence:paper:quantity",
            "text": quantified,
            "text_start": 0,
            "selectors": [_selector("E1:S1", quantified, 0)],
        },
        {
            "evidence_id": "evidence:paper:relation",
            "text": relation,
            "text_start": 0,
            "selectors": [_selector("E2:S1", relation, 0)],
        },
    ]

    observation = candidate_evidence_set_binding(records, question)

    assert observation["binding_status"] == "bound"
    assert observation["polarity_signal"] == "undetermined"
    assert observation["support_evidence_refs"] == []
    assert observation["explicit_contradiction_evidence_refs"] == []


def test_candidate_prompt_cannot_add_spans_outside_supplied_pack() -> None:
    question = "Are the automatically constructed datasets subject to quality control?"
    prefix = "Automatically generated datasets permit controlled experiments. "
    gap = "Unrelated discussion. " * 80
    decisive = (
        "It is much harder to validate the quality of such data at scale, and only "
        "small validation studies are left for future work."
    )
    source_text = prefix + gap + decisive
    prompt = _candidate_prompt(
        question,
        [
            {
                "label": "E1",
                "evidence_id": "evidence:paper:quality",
                "text": prefix,
                "text_start": 0,
                "candidate_source_text": source_text,
                "selectors": [_selector("E1:S1", prefix.strip(), 0)],
            }
        ],
        required_slots=[],
    )

    assert decisive not in prompt
    assert prefix.strip() in prompt
    assert "CANDIDATE DECISION RULES:" in prompt
    assert "incompatible definition or mutually exclusive scope" in prompt
