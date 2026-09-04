from __future__ import annotations

import hashlib
from types import SimpleNamespace
from typing import Any

from ktem.docqa.canonical_proposition_evidence_candidates import (
    enumerate_canonical_evidence_candidates,
)
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.reasoning.mara_qasper_candidate_prompt import (
    _prioritized_candidate_prompt_evidence,
)
from ktem.reasoning.mara_qasper_selector_lineage import qasper_selector_crosswalk
from ktem.reasoning.mara_qasper_semantic_pack import (
    prepare_qasper_canonical_records_with_trace,
)
from ktem.reasoning.mara_semantic_proposition_packing import (
    pack_semantic_proposition_evidence,
)
from ktem.reasoning.mara_semantic_proposition_span_selectors import (
    canonical_span_selector_projection,
    canonical_span_selectors,
)


def test_span_projection_records_every_pre_limit_decision_without_changing_output() -> (
    None
):
    text = (
        "The authors introduce a model. "
        "They inspect its learned representations. "
        "An unrelated baseline is reported. "
        "The analysis associates image regions with entity words. "
        "Further implementation details follow."
    )
    question = (
        "Did the authors inspect whether the model learned to associate "
        "image parts with entity words?"
    )

    selectors, trace = canonical_span_selector_projection(
        "E1",
        text,
        100,
        None,
        selector_max_chars=640,
        question=question,
        max_selectors=2,
    )

    assert selectors == canonical_span_selectors(
        "E1",
        text,
        100,
        None,
        selector_max_chars=640,
        question=question,
        max_selectors=2,
    )
    assert trace["contract_id"] == "canonical_span_selector_projection.v1"
    assert trace["complete"] is True
    assert trace["input_span_count"] == 5
    assert trace["selected_span_count"] == 2
    assert trace["decision_count"] == trace["input_span_count"]
    assert sum(decision["selected"] for decision in trace["decisions"]) == 2
    assert {
        decision["decision"]
        for decision in trace["decisions"]
        if not decision["selected"]
    } == {"per_record_selector_limit"}
    assert all(
        len(decision["span_identity_digest"]) == 64 for decision in trace["decisions"]
    )


def test_source_and_window_projections_close_every_input_boundary() -> None:
    request = SimpleNamespace(
        query_plan={
            "evidence_slots": [
                {
                    "required_for_verification": True,
                    "slot_id": "support:boolean_proposition",
                    "evidence_ids": [],
                }
            ]
        }
    )
    bundle = EvidenceBundle(
        route="text_rag",
        items=[
            {
                "evidence_id": "one",
                "source_id": "paper",
                "text": "The authors compare the two systems.",
            },
            {
                "evidence_id": "two",
                "source_id": "paper",
                "text": "The second system is a baseline.",
            },
        ],
    )

    packing = pack_semantic_proposition_evidence(
        request,
        "Did the authors compare the two systems?",
        [{"slot_id": "support:boolean_proposition", "description": "support"}],
        bundle,
        candidate_priority=True,
    )

    assert len(packing.source_decisions) == len(bundle.items)
    assert all(decision["reason"] for decision in packing.source_decisions)
    selection = [
        decision
        for decision in packing.window_decisions
        if decision["stage"] == "window_selection"
    ]
    fitting = [
        decision
        for decision in packing.window_decisions
        if decision["stage"] == "fit_to_input_budget"
    ]
    assert selection
    assert len(fitting) == sum(decision["selected"] for decision in selection)
    assert all(decision["reason"] for decision in packing.window_decisions)


def test_canonical_projection_records_specific_selector_rejection_reasons() -> None:
    text = "The paper uses the method."
    records = [
        {
            "label": "E1",
            "evidence_id": "evidence-1",
            "text": text,
            "text_start": 0,
            "selectors": [
                {
                    "selector_id": "E1:S1",
                    "text": text,
                    "span_start": 0,
                    "span_end": len(text),
                },
                {
                    "selector_id": "E1:S2",
                    "text": "wrong",
                    "span_start": 0,
                    "span_end": 5,
                },
            ],
        }
    ]

    projected, trace = prepare_qasper_canonical_records_with_trace(
        "Does the paper use the method?",
        records,
    )

    assert projected
    assert trace["complete"] is True
    assert trace["decision_count"] == trace["input_selector_count"] == 2
    assert {decision["reason"] for decision in trace["decisions"]} == {
        "selected_for_canonical_selector_universe",
        "exact_selector_invalid",
    }


def test_candidate_projection_records_semantic_filter_and_cap_decisions() -> None:
    text = (
        "The authors introduce a model. "
        "They inspect its learned representations. "
        "An unrelated baseline is reported. "
        "The analysis associates image regions with entity words. "
        "Training examples show related visual and textual behavior."
    )
    records = _prioritized_candidate_prompt_evidence(
        [
            {
                "label": "E1",
                "evidence_id": "evidence-1",
                "text": text,
                "text_start": 0,
                "candidate_source_text": text,
                "candidate_source_text_start": 0,
                "canonical_start": None,
                "selectors": [],
            }
        ],
        (
            "Did the authors inspect whether the model learned to associate "
            "image parts with entity words?"
        ),
    )

    record = records[0]
    trace = record["candidate_selector_projection_trace"]
    selected_refs = [selector["selector_id"] for selector in record["selectors"]]
    assert trace["contract_id"] == "qasper_candidate_selector_projection.v1"
    assert trace["complete"] is True
    assert trace["decision_count"] == trace["input_selector_count"]
    assert trace["eligible_selector_count"] >= trace["selected_selector_count"]
    assert trace["selected_selector_refs"] == selected_refs
    assert [
        decision["selector_id"]
        for decision in sorted(
            (decision for decision in trace["decisions"] if decision["selected"]),
            key=lambda decision: decision["eligible_rank"],
        )
    ] == selected_refs
    assert all(decision["decision"] for decision in trace["decisions"])


def test_selector_crosswalk_uses_offsets_and_digests_not_reused_labels() -> None:
    source_records = [
        {
            "label": "E1",
            "evidence_id": "evidence-1",
            "text": "Beta.",
            "text_start": 10,
            "selectors": [
                {
                    "selector_id": "E1:S1",
                    "text": "Beta.",
                    "span_start": 10,
                    "span_end": 15,
                }
            ],
        }
    ]
    canonical_records = [
        {
            "label": "E1",
            "evidence_id": "evidence-1",
            "text": "Alpha. Beta. Gamma.",
            "text_start": 0,
            "candidate_selector_projection_trace": {
                "contract_id": "qasper_candidate_selector_projection.v1",
                "complete": True,
                "input_selector_count": 3,
                "eligible_selector_count": 3,
                "selected_selector_count": 2,
                "decision_count": 3,
                "selected_selector_refs": ["E1:S2", "E1:S3"],
                "decisions": [
                    {
                        "selector_id": "E1:S2",
                        "span_start": 10,
                        "span_end": 15,
                        "text_digest": hashlib.sha256(b"Beta.").hexdigest(),
                        "selected": True,
                    },
                    {
                        "selector_id": "E1:S3",
                        "span_start": 16,
                        "span_end": 22,
                        "text_digest": hashlib.sha256(b"Gamma.").hexdigest(),
                        "selected": True,
                    },
                ],
            },
            "selectors": [
                {
                    "selector_id": "E1:S2",
                    "text": "Beta.",
                    "span_start": 10,
                    "span_end": 15,
                },
                {
                    "selector_id": "E1:S3",
                    "text": "Gamma.",
                    "span_start": 16,
                    "span_end": 22,
                },
            ],
        }
    ]

    crosswalk = qasper_selector_crosswalk(source_records, canonical_records)

    assert crosswalk["contract_id"] == "qasper_selector_crosswalk.v1"
    assert crosswalk["complete"] is True
    assert crosswalk["canonical_selector_count"] == 2
    assert crosswalk["mapped_canonical_selector_count"] == 2
    exact, reenumerated = crosswalk["canonical_selectors"]
    assert exact["canonical_selector_ref"] == "E1:S2"
    assert exact["source_selector_refs"] == ["E1:S1"]
    assert exact["origin"] == "source_window_selector"
    assert reenumerated["canonical_selector_ref"] == "E1:S3"
    assert reenumerated["source_selector_refs"] == []
    assert reenumerated["origin"] == "candidate_source_reenumeration"
    assert reenumerated["source_window_status"] == "outside_packed_window"


def test_selector_crosswalk_rejects_a_reused_ref_with_different_span_identity() -> None:
    source_records = [
        {
            "evidence_id": "evidence-1",
            "text": "Beta.",
            "text_start": 10,
            "selectors": [
                {
                    "selector_id": "E1:S1",
                    "text": "Beta.",
                    "span_start": 10,
                    "span_end": 15,
                }
            ],
        }
    ]
    canonical_records = [
        {
            "evidence_id": "evidence-1",
            "text": "Gamma.",
            "text_start": 16,
            "candidate_selector_projection_trace": {
                "complete": True,
                "selected_selector_refs": ["E1:S1"],
                "decisions": [
                    {
                        "selector_id": "E1:S1",
                        "span_start": 10,
                        "span_end": 15,
                        "text_digest": hashlib.sha256(b"Beta.").hexdigest(),
                        "selected": True,
                    }
                ],
            },
            "selectors": [
                {
                    "selector_id": "E1:S1",
                    "text": "Gamma.",
                    "span_start": 16,
                    "span_end": 22,
                }
            ],
        }
    ]

    crosswalk = qasper_selector_crosswalk(source_records, canonical_records)

    assert crosswalk["complete"] is False
    assert crosswalk["mapped_canonical_selector_count"] == 0
    assert crosswalk["canonical_selectors"][0]["origin"] == (
        "canonical_projection_unattributed"
    )


def test_plan_enumeration_records_every_relation_decision() -> None:
    selectors = [
        {
            "selector_id": "E1:S1",
            "event_id": "event-1",
            "span_start": 0,
            "span_end": 10,
            "slot_hints": ["actor", "predicate"],
            "object_tokens": [],
            "predicate_match_kind": "exact",
        },
        {
            "selector_id": "E1:S2",
            "event_id": "event-1",
            "span_start": 11,
            "span_end": 20,
            "slot_hints": ["object"],
            "object_tokens": ["model"],
            "predicate_match_kind": "missing",
        },
    ]

    def analyze(
        selected: tuple[dict[str, Any], ...],
        relation: str,
    ) -> dict[str, Any]:
        covered_slots = sorted(
            {slot for selector in selected for slot in selector["slot_hints"]}
        )
        covered_tokens = sorted(
            {token for selector in selected for token in selector["object_tokens"]}
        )
        return {
            "valid": False,
            "reason": "fixture_rejection",
            "rejection_reasons": ["fixture_rejection"],
            "required_slots": ["actor", "predicate", "object"],
            "covered_slots": covered_slots,
            "required_object_tokens": ["model"],
            "covered_object_tokens": covered_tokens,
            "event_ids": ["event-1"],
            "event_subplans": [],
            "exact_predicate_count": int(relation == "proposition_support"),
        }

    enumeration = enumerate_canonical_evidence_candidates(
        selectors,
        ("actor", "predicate", "object"),
        ("model",),
        analyze=analyze,
    )
    trace = enumeration.trace

    assert trace["candidate_decisions_complete"] is True
    assert trace["enumeration_policy_complete"] is True
    assert len(trace["enumeration_policy_digest"]) == 64
    assert trace["enumeration_policy"]["local"]["enumerated_candidate_count"] == 3
    assert trace["enumeration_policy"]["local"]["not_attempted_candidate_count"] == 0
    assert trace["candidate_decision_count"] == trace["relation_analysis_count"]
    assert len(trace["candidate_decisions_digest"]) == 64
    assert len({row["candidate_id"] for row in trace["candidate_decisions"]}) == (
        trace["candidate_decision_count"]
    )
    assert {row["relation"] for row in trace["candidate_decisions"]} == {
        "proposition_support",
        "explicit_contradiction",
    }
    assert all(row["decision"] == "rejected" for row in trace["candidate_decisions"])
    assert {row["origin"] for row in trace["candidate_decisions"]} == {"event_local"}
    assert all(
        row["rejection_reasons"] == ["fixture_rejection"]
        for row in trace["candidate_decisions"]
    )
