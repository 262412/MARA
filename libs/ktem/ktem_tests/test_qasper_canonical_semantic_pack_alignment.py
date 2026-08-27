from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from jsonschema import ValidationError, validate
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.qasper_semantic_pack_contract import (
    qasper_semantic_pack_continuity_reason,
)
from ktem.reasoning.mara_qasper_candidate_evidence import candidate_evidence_set_binding
from ktem.reasoning.mara_qasper_semantic_pack import (
    freeze_qasper_canonical_semantic_pack,
    load_qasper_canonical_semantic_pack,
    prepare_qasper_canonical_records,
    qasper_canonical_span_universe_digest,
)
from ktem.reasoning.mara_semantic_proposition_packing import (
    pack_semantic_proposition_evidence,
    required_semantic_proposition_slots,
)
from ktem.reasoning.mara_semantic_proposition_schema import (
    parse_semantic_proposition_response,
    semantic_proposition_response_format,
)
from ktem.reasoning.mara_semantic_proposition_verifier import (
    _candidate_context,
    build_semantic_proposition_verifier,
)


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


def _bundle(texts: list[str]) -> EvidenceBundle:
    return EvidenceBundle(
        route="doc_text",
        items=[
            {
                "evidence_id": f"chunk-{index}",
                "source_id": "paper",
                "text": text,
            }
            for index, text in enumerate(texts, start=1)
        ],
    )


def _selector(selector_id: str, text: str, start: int = 0) -> dict[str, Any]:
    return {
        "selector_id": selector_id,
        "text": text,
        "span_start": start,
        "span_end": start + len(text),
    }


def test_canonical_pack_preserves_a_locally_valid_cross_span_relation_set() -> None:
    question = "Did the authors compare the two systems?"
    records = [
        {
            "evidence_id": "evidence-1",
            "text": "The authors compared the two systems",
            "selectors": [
                _selector("E1:S1", "The authors", 0),
                _selector("E1:S2", "compared", 12),
                _selector("E1:S3", "the two systems", 21),
            ],
        }
    ]

    canonical = prepare_qasper_canonical_records(question, records)
    binding = candidate_evidence_set_binding(canonical, question)

    assert binding["support"] is True
    assert binding["evidence_refs"] == ["E1:S1", "E1:S2", "E1:S3"]
    selectors = canonical[0]["selectors"]
    assert [selector["allowed_proposition_slots"] for selector in selectors] == [
        ["actor"],
        ["predicate"],
        ["object", "quantifier"],
    ]
    assert selectors[1]["local_relation_state"] == "affirmative_assertion"


def test_canonical_pack_keeps_partial_relation_anchor_without_upgrading_object() -> None:
    question = "Did the authors release the code for the evaluated system?"
    text = "The authors released it."
    records = [
        {
            "evidence_id": "evidence-1",
            "text": text,
            "selectors": [_selector("E1:S1", text)],
        }
    ]

    canonical = prepare_qasper_canonical_records(question, records)

    [record] = canonical
    [selector] = record["selectors"]
    assert selector["relation_bearing"] is True
    assert selector["allowed_proposition_slots"] == ["actor", "predicate"]
    assert "object" not in selector["allowed_proposition_slots"]


def test_frozen_pack_round_trip_preserves_exact_span_universe() -> None:
    question = "Did the authors compare the two systems?"
    request = _request(question)
    bundle = _bundle(["The authors compared the two systems."])
    slots = required_semantic_proposition_slots(request)
    source = pack_semantic_proposition_evidence(
        request,
        question,
        slots,
        bundle,
        candidate_priority=True,
    )

    frozen = freeze_qasper_canonical_semantic_pack(
        bundle,
        question=question,
        slots=slots,
        source_packing=source,
        records=prepare_qasper_canonical_records(question, source.records),
        candidate_transaction_id="candidate-transaction-1",
    )
    expected_universe = qasper_canonical_span_universe_digest(frozen.records)

    bundle.items.append(
        {
            "evidence_id": "late-chunk",
            "source_id": "paper",
            "text": "Late evidence that the candidate never saw.",
        }
    )
    loaded, reason = load_qasper_canonical_semantic_pack(
        bundle,
        question=question,
        candidate_transaction_id="candidate-transaction-1",
    )

    assert reason == ""
    assert loaded is not None
    assert loaded.semantic_pack_digest == frozen.semantic_pack_digest
    assert qasper_canonical_span_universe_digest(loaded.records) == expected_universe
    assert all(
        record["evidence_id"] != "evidence:paper:late-chunk"
        for record in loaded.records
    )


def test_frozen_pack_fails_closed_when_span_universe_is_mutated() -> None:
    question = "Did the authors compare the two systems?"
    request = _request(question)
    bundle = _bundle(["The authors compared the two systems."])
    slots = required_semantic_proposition_slots(request)
    source = pack_semantic_proposition_evidence(
        request,
        question,
        slots,
        bundle,
        candidate_priority=True,
    )
    freeze_qasper_canonical_semantic_pack(
        bundle,
        question=question,
        slots=slots,
        source_packing=source,
        records=prepare_qasper_canonical_records(question, source.records),
        candidate_transaction_id="candidate-transaction-1",
    )
    bundle.metadata["qasper_canonical_semantic_pack"]["records"][0]["selectors"][0][
        "text"
    ] = "changed after candidate generation"

    loaded, reason = load_qasper_canonical_semantic_pack(
        bundle,
        question=question,
        candidate_transaction_id="candidate-transaction-1",
    )

    assert loaded is None
    assert reason == "canonical_semantic_pack_identity_mismatch"


def _continuity_case() -> tuple[str, EvidenceBundle, dict[str, Any]]:
    question = "Did the authors compare the two systems?"
    request = _request(question)
    bundle = _bundle(["The authors compared the two systems."])
    slots = required_semantic_proposition_slots(request)
    source = pack_semantic_proposition_evidence(
        request,
        question,
        slots,
        bundle,
        candidate_priority=True,
    )
    frozen = freeze_qasper_canonical_semantic_pack(
        bundle,
        question=question,
        slots=slots,
        source_packing=source,
        records=prepare_qasper_canonical_records(question, source.records),
        candidate_transaction_id="candidate-transaction-1",
    )
    [record] = frozen.records
    [selector] = record["selectors"]
    span_digest = qasper_canonical_span_universe_digest(frozen.records)
    identity = {
        "semantic_pack_digest": frozen.semantic_pack_digest,
        "span_universe_digest": span_digest,
        "candidate_transaction_id": "candidate-transaction-1",
    }
    bundle.metadata["qasper_candidate_generation"] = {
        "transaction_id": "candidate-transaction-1",
        "canonical_semantic_pack_digest": frozen.semantic_pack_digest,
        "canonical_span_universe_digest": span_digest,
        "candidate_evidence_set_binding": bundle.metadata[
            "qasper_canonical_semantic_pack"
        ]["proposition_binding"],
        "required_slots": bundle.metadata["qasper_canonical_semantic_pack"]["slots"],
    }
    bundle.metadata["semantic_proposition_verifier"] = {
        "semantic_pack_digest": frozen.semantic_pack_digest,
        "canonical_span_universe_digest": span_digest,
        "candidate_transaction_id": "candidate-transaction-1",
        "canonical_pack_continuity_status": "preserved",
    }
    response: dict[str, Any] = {
        "verdict": "yes",
        "premises": [
            {
                "evidence_id": record["evidence_id"],
                "span_selector": selector["selector_id"],
                "quote": selector["text"],
                "span_start": selector["span_start"],
                "span_end": selector["span_end"],
                "binds_proposition_slots": selector["allowed_proposition_slots"],
            }
        ],
        "verifier": {
            "semantic_pack_digest": frozen.semantic_pack_digest,
            "canonical_span_universe_digest": span_digest,
            "candidate_transaction_id": "candidate-transaction-1",
            "canonical_pack_continuity_status": "preserved",
        },
        "entailment_audit": {"semantic_pack_identity": identity},
    }
    return question, bundle, response


def test_authority_rejects_any_stage_that_changes_the_frozen_object() -> None:
    question, bundle, response = _continuity_case()

    assert (
        qasper_semantic_pack_continuity_reason(
            bundle,
            question=question,
            response=response,
        )
        == ""
    )

    response["premises"][0]["quote"] = "evidence added after candidate generation"
    assert (
        qasper_semantic_pack_continuity_reason(
            bundle,
            question=question,
            response=response,
        )
        == "canonical_semantic_pack_selection_mismatch"
    )


def test_authority_rejects_candidate_required_slots_that_diverge_from_pack() -> None:
    question, bundle, response = _continuity_case()
    bundle.metadata["qasper_candidate_generation"]["required_slots"] = []

    assert (
        qasper_semantic_pack_continuity_reason(
            bundle,
            question=question,
            response=response,
        )
        == "canonical_semantic_pack_stage_identity_mismatch"
    )


def test_verifier_reuses_frozen_pack_and_ignores_late_bundle_evidence() -> None:
    question = "Did the authors compare the two systems?"
    request = _request(question)
    bundle = _bundle(["The authors compared the two systems."])
    slots = required_semantic_proposition_slots(request)
    source = pack_semantic_proposition_evidence(
        request,
        question,
        slots,
        bundle,
        candidate_priority=True,
    )
    frozen = freeze_qasper_canonical_semantic_pack(
        bundle,
        question=question,
        slots=slots,
        source_packing=source,
        records=prepare_qasper_canonical_records(question, source.records),
        candidate_transaction_id="candidate-transaction-1",
    )
    bundle.metadata["qasper_candidate_generation"] = {
        "transaction_id": "candidate-transaction-1"
    }
    bundle.items.append(
        {
            "evidence_id": "late",
            "source_id": "paper",
            "text": "Late evidence that the candidate did not see.",
        }
    )

    context = _candidate_context(
        SimpleNamespace(
            llm=SimpleNamespace(model_name="proposal"),
            audit_llm=SimpleNamespace(model_name="auditor"),
            release_mode=True,
        ),
        request,
        question,
        "yes",
        bundle,
    )

    assert context["pack_failure_reason"] == ""
    assert context["packing"].records == frozen.records
    assert (
        context["slots"] == bundle.metadata["qasper_canonical_semantic_pack"]["slots"]
    )
    assert all(
        slot["proposition_binding_digest"]
        == bundle.metadata["qasper_canonical_semantic_pack"][
            "proposition_binding_digest"
        ]
        for slot in context["slots"]
    )
    assert all(
        record["evidence_id"] != "evidence:paper:late"
        for record in context["packing"].records
    )
    identity = bundle.metadata["semantic_candidate_transaction_identity"]
    assert identity["candidate_transaction_id"] == "candidate-transaction-1"
    assert identity["canonical_pack_continuity_status"] == "preserved"


def test_missing_frozen_pack_stops_before_any_verifier_provider_call() -> None:
    class RecordingLLM:
        model_name = "proposal"

        def __init__(self) -> None:
            self.call_count = 0

        def __call__(self, *_args: Any, **_kwargs: Any) -> Any:
            self.call_count += 1
            raise AssertionError("provider must not be called")

    llm = RecordingLLM()
    verifier = build_semantic_proposition_verifier(
        SimpleNamespace(
            answering_pipeline=SimpleNamespace(llm=llm),
            semantic_entailment_auditor_llm=RecordingLLM(),
        )
    )
    assert verifier is not None
    bundle = _bundle(["The authors compared the two systems."])

    result = verifier(
        _request("Did the authors compare the two systems?"),
        "Did the authors compare the two systems?",
        "yes",
        bundle,
    )

    assert result is None
    assert llm.call_count == 0
    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["reason"] == "canonical_semantic_pack_missing"
    assert trace["verifier_execution_status"] == "not_started"
    assert trace["auditor_execution_status"] == "not_started"


def test_verifier_schema_physically_binds_selector_to_local_slots() -> None:
    allowed = {
        "E1:S1": ("actor",),
        "E1:S2": ("predicate", "object", "quantifier"),
    }
    response_format = semantic_proposition_response_format(
        list(allowed),
        ["support:boolean_proposition"],
        candidate="yes",
        applicable_proposition_slots=("actor", "predicate", "object", "quantifier"),
        allowed_proposition_slot_bindings=allowed,
    )
    schema = response_format["json_schema"]["schema"]
    payload: dict[str, Any] = {
        "candidate_judgment": "supported",
        "support_mode": "evidence_set",
        "jointly_complete": True,
        "each_premise_required": True,
        "not_applicable_proposition_slots": [],
        "premises": [
            {
                "span_selector": "E1:S1",
                "proposition_fragment": "The authors",
                "supports_slot_ids": ["support:boolean_proposition"],
                "binds_proposition_slots": ["actor"],
            },
            {
                "span_selector": "E1:S2",
                "proposition_fragment": "compared the two systems",
                "supports_slot_ids": ["support:boolean_proposition"],
                "binds_proposition_slots": ["predicate", "object", "quantifier"],
            },
        ],
    }
    packed = [
        {
            "evidence_id": "evidence-1",
            "selectors": [
                _selector("E1:S1", "The authors"),
                _selector("E1:S2", "compared the two systems", 12),
            ],
        }
    ]

    validate(instance=payload, schema=schema)
    parsed = parse_semantic_proposition_response(
        json.dumps(payload),
        packed=packed,
        slot_ids={"support:boolean_proposition"},
        model="test-model",
        seed=7,
        candidate="yes",
        applicable_proposition_slots=("actor", "predicate", "object", "quantifier"),
        allowed_proposition_slot_bindings=allowed,
    )
    assert parsed.value is not None

    payload["premises"][0]["binds_proposition_slots"] = [
        "actor",
        "predicate",
        "object",
        "quantifier",
    ]
    with pytest.raises(ValidationError):
        validate(instance=payload, schema=schema)
    rejected = parse_semantic_proposition_response(
        json.dumps(payload),
        packed=packed,
        slot_ids={"support:boolean_proposition"},
        model="test-model",
        seed=7,
        candidate="yes",
        applicable_proposition_slots=("actor", "predicate", "object", "quantifier"),
        allowed_proposition_slot_bindings=allowed,
    )
    assert rejected.failure_reason == "premise_proposition_binding_not_allowed"


@pytest.mark.parametrize(
    ("question", "spans", "required_feature"),
    [
        (
            "Did they collected the two datasets?",
            [
                "We used two datasets in the experiments.",
                "The authors collected CreateDebate, but FBFans came from an existing source.",
            ],
            "quantifier",
        ),
        (
            "Do they add one latent variable for each language pair in their Bayesian model?",
            [
                "We use one joint Bayesian model.",
                "For each language pair, we add a crosslingual latent variable.",
            ],
            "quantifier",
        ),
        (
            "Does this method help in sentiment classification task improvement?",
            [
                "We evaluate the method on sentiment classification.",
                "It yields large improvements on that downstream task.",
            ],
            "cross_span",
        ),
        (
            "Do they inspect their model to see if their model learned to associate image parts with words related to entities?",
            [
                "The authors visualize the modality attention of their model.",
                "The visualization links image regions with entity-related words.",
            ],
            "paraphrase",
        ),
        (
            "Is car-speak language collection of abstract features that classifier is later trained on?",
            [
                "Car-speak is abstract language about vehicle attributes.",
                "The classifier is trained on review vectors, not on car-speak features.",
            ],
            "cross_span",
        ),
        (
            "Are the automatically constructed datasets subject to quality control?",
            [
                "We inspect automatically constructed probes to ensure their quality.",
                "The generated datasets are carefully controlled for annotation artifacts.",
            ],
            "entity_alias",
        ),
    ],
)
def test_six_natural_questions_expose_auditable_structural_features(
    question: str,
    spans: list[str],
    required_feature: str,
) -> None:
    records = [
        {
            "evidence_id": f"evidence-{index}",
            "text": text,
            "selectors": [_selector(f"E{index}:S1", text)],
        }
        for index, text in enumerate(spans, start=1)
    ]

    canonical = prepare_qasper_canonical_records(question, records)
    binding = candidate_evidence_set_binding(canonical, question)

    assert canonical
    assert binding["binding_status"] == "bound"
    assert 1 <= len(binding["evidence_refs"]) <= 4
    assert binding["relation_anchor_refs"]
    assert required_feature in binding["structural_features"]
