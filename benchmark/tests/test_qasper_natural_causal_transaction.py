from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from typing import Any

from benchmark.qasper_causal_transaction_stages import _retrieval_payload
from scripts.slurm.qasper_natural_causal_transaction import _local_replay_prediction

_EXPECTED_RETRIEVAL_DIGEST_FIELDS = [
    "production_input_records_digest",
    "ranking_digest",
    "ranking_records_digest",
    "raw_retrieval_records_digest",
    "retrieval_trace_digest",
    "retrieval_trace_semantic_digest",
    "retrieval_trace_telemetry_digest",
]


def _evidence(evidence_id: str, text: str) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "text": text,
    }


def test_local_replay_keeps_retrieval_envelope_separate_from_candidate_snapshot() -> (
    None
):
    retrieval_items = [
        _evidence("evidence-a", "First retrieved passage."),
        _evidence("evidence-b", "Second retrieved passage."),
        _evidence("evidence-c", "Third retrieved passage."),
    ]
    candidate_items = [
        deepcopy(retrieval_items[2]),
        deepcopy(retrieval_items[0]),
        deepcopy(retrieval_items[1]),
    ]
    source_snapshot = {
        "contract_id": "semantic_source_input_snapshot.v1",
        "complete": True,
        "source_items": [
            {"source_item_index": index, "evidence_id": item["evidence_id"]}
            for index, item in enumerate(candidate_items, start=1)
        ],
    }
    source_packing = {
        "contract_id": "qasper_source_packing_observation.v1",
        "source_input_snapshot": source_snapshot,
    }
    candidate_pack = {"source_packing_observation": source_packing}
    row = {
        "example_id": "stage-two-envelope-characterization",
        "route": "text_rag",
        "question": "Was the method evaluated?",
        "gold_answers": ["yes"],
        "retrieved_hits": deepcopy(retrieval_items),
        "retrieval_trace": [{"stage": "hybrid_retrieval", "count": 3}],
        "evidence_bundle": {
            "items": deepcopy(retrieval_items),
            "metadata": {"retrieval_contract": "production-input.v1"},
        },
        "evidence_metadata": {"query_plan": {"plan_id": "retrieval-plan"}},
    }
    context = SimpleNamespace(
        bundle=SimpleNamespace(
            items=candidate_items,
            metadata={
                "candidate_ranked_evidence": [
                    {"canonical_id": item["evidence_id"]} for item in candidate_items
                ],
                "qasper_canonical_semantic_pack": candidate_pack,
            },
        ),
        binding={"plan_construction_trace": {"status": "passed"}},
        candidate_generation={"status": "parsed"},
        slots=[],
    )
    original_bundle = deepcopy(row["evidence_bundle"])

    replay_prediction = _local_replay_prediction(row, context)
    reference_stage = _retrieval_payload(row)
    replay_stage = _retrieval_payload(replay_prediction)

    assert replay_prediction["evidence_bundle"] == original_bundle
    assert row["evidence_bundle"] == original_bundle
    digest_fields = sorted(key for key in reference_stage if key.endswith("_digest"))
    assert digest_fields == _EXPECTED_RETRIEVAL_DIGEST_FIELDS
    assert {key: replay_stage[key] for key in digest_fields} == {
        key: reference_stage[key] for key in digest_fields
    }
    candidate_source = replay_prediction["evidence_metadata"][
        "semantic_proposition_verifier"
    ]["semantic_data_lineage"]["source_packing"]
    assert candidate_source == source_packing
    assert [
        item["evidence_id"]
        for item in candidate_source["source_input_snapshot"]["source_items"]
    ] == ["evidence-c", "evidence-a", "evidence-b"]
