import pytest

from benchmark.answer_finalizer import attach_structured_citations_from_evidence
from benchmark.citation_locators import CitationLocator
from benchmark.citation_stage_projection import _citation_matches_item
from benchmark.contract_invariant_metrics import contract_invariant_summary
from benchmark.evidence_identity_metrics import reranker_lineage
from benchmark.headline_policy import headline_policy_predictions
from benchmark.repair_plan import CONTRACT_GATES, evaluate_release_gates
from benchmark.report_identity_compaction import compact_identity_evidence_list


def test_citation_kind_must_match_evidence_kind():
    item = {
        "source_id": "paper",
        "page_label": "5",
        "cell_id": "shared-local-id",
        "evidence_level": "cell",
    }

    assert not _citation_matches_item(
        {
            "kind": "element",
            "evidence_id": "cell:paper:shared-local-id",
            "source_id": "paper",
            "page_label": "5",
        },
        item,
    )


@pytest.mark.parametrize(
    ("kind", "page_label"),
    [("page", "5"), ("source", "")],
)
def test_page_locator_identity_round_trip(kind: str, page_label: str):
    record = CitationLocator(
        kind=kind,
        source_id="paper",
        page_label=page_label,
    ).page_evidence_record()

    assert record["canonical_id"] == (
        f"page:paper:{page_label}" if page_label else "source:paper:source"
    )
    from ktem.docqa.evidence_identity import identity_of

    assert identity_of(record).key == record["canonical_id"]


def test_generic_citation_fallback_unions_all_verified_support():
    items = [
        {
            "evidence_id": "left",
            "source_id": "paper",
            "page_label": "4",
            "text": "Left claim.",
        },
        {
            "evidence_id": "right",
            "source_id": "paper",
            "page_label": "9",
            "text": "Right claim.",
        },
    ]
    prediction = {
        "evidence_bundle": {
            "items": items,
            "metadata": {"verified_claim_support_evidence": items},
        },
        "evidence_metadata": {},
    }

    citations = attach_structured_citations_from_evidence(prediction, span="answer")

    assert [(item["source_id"], item["page_label"]) for item in citations] == [
        ("paper", "4"),
        ("paper", "9"),
    ]


def test_reranker_lineage_rejects_same_page_text_with_different_identity():
    candidate = {
        "source_id": "paper",
        "page_label": "5",
        "cell_id": "cell-a",
        "text": "10",
    }
    reranked = {
        "source_id": "paper",
        "page_label": "5",
        "cell_id": "cell-b",
        "text": "10",
    }

    coverage, violations = reranker_lineage([candidate], [reranked])

    assert coverage == 0.0
    assert violations == 1


def test_compact_artifact_preserves_atomic_identity_and_stages():
    item = {
        "identity": {
            "source_id": "paper",
            "kind": "span",
            "local_id": "span-1",
        },
        "canonical_id": "span:paper:span-1",
        "source_id": "paper",
        "span_id": "span-1",
        "evidence_level": "span",
        "retrieval_lineage": [{"retriever_name": "dense", "raw_rank": 1}],
        "representations": [{"modality": "ocr", "text": "support"}],
    }

    for stage in (
        "canonical_candidate_evidence",
        "fused_evidence",
        "reranker_input_evidence",
        "reranked_evidence",
    ):
        projected = compact_identity_evidence_list([item], stage)
        assert projected is not None
        assert projected[0]["identity"] == item["identity"]
        assert projected[0]["span_id"] == "span-1"
        assert projected[0]["evidence_level"] == "span"
        assert projected[0]["retrieval_lineage"] == item["retrieval_lineage"]
        assert projected[0]["representations"] == item["representations"]


def test_headline_policy_fails_closed_without_exactly_one_deployed_route():
    with pytest.raises(ValueError, match="exactly one deployed_policy"):
        headline_policy_predictions(
            [
                {"route": "text", "headline_role": "baseline"},
                {"route": "hybrid", "headline_role": "diagnostic"},
            ]
        )
    with pytest.raises(ValueError, match="exactly one deployed_policy"):
        headline_policy_predictions(
            [
                {"route": "text", "headline_role": "deployed_policy"},
                {"route": "hybrid", "headline_role": "deployed_policy"},
            ]
        )


def test_paired_regression_aligns_examples_instead_of_subtracting_means():
    phase_b = {
        "primary_score": 0.9,
        "per_example_metric_records": [
            {
                "dataset": "d",
                "example_id": "shared",
                "route": "controller",
                "primary_score": 0.2,
            },
            {
                "dataset": "d",
                "example_id": "baseline-only",
                "route": "controller",
                "primary_score": 1.0,
            },
        ],
    }
    phase_g = {
        "primary_score": 0.1,
        "per_example_metric_records": [
            {
                "dataset": "d",
                "example_id": "shared",
                "route": "controller",
                "primary_score": 0.4,
            },
            {
                "dataset": "d",
                "example_id": "candidate-only",
                "route": "controller",
                "primary_score": 0.0,
            },
        ],
    }

    result = evaluate_release_gates(
        phase_b=phase_b,
        phase_g=phase_g,
        paired_semantic_ci_low=0.01,
    )

    assert result["deployed_native_score_delta"]["value"] == 0.2
    assert result["deployed_native_score_delta"]["paired_example_count"] == 1
    assert result["deployed_native_score_delta"]["paired_wins"] == 1
    assert result["deployed_native_score_delta"]["paired_losses"] == 0
    assert result["deployed_native_score_delta"]["paired_ci_low"] == 0.2
    assert result["deployed_native_score_delta"]["paired_ci_high"] == 0.2
    assert result["semantic_f1_delta_pp"]["release_blocking"] is False
    assert result["semantic_f1_ci_low"]["release_blocking"] is False


def test_contract_gates_cover_evidence_invariants():
    metrics = {gate.metric for gate in CONTRACT_GATES}

    assert {
        "identity_collision_count",
        "runtime_benchmark_roundtrip",
        "citation_provenance_violation_count",
        "reranker_lineage_violation_count",
        "missing_execution_slot_answer_count",
    } <= metrics


def test_contract_invariant_summary_measures_runtime_artifact_contracts():
    item = {
        "evidence_id": "cell-parent",
        "source_id": "paper",
        "page_label": "5",
        "cell_id": "cell-1",
        "evidence_level": "cell",
        "row_label": "Revenue",
        "period": "2023",
        "value": "10",
    }
    prediction = {
        "predicted_answer": "10",
        "evidence_metadata": {
            "candidate_evidence": [item],
            "reranker_input_evidence": [item],
            "reranked_evidence": [item],
            "emitted_citation_evidence": [item],
            "query_plan": {
                "evidence_slots": [
                    {
                        "slot_id": "operand:revenue",
                        "required_for_execution": True,
                        "status": "filled",
                        "evidence_ids": ["cell:paper:cell-1"],
                    }
                ]
            },
        },
    }

    assert contract_invariant_summary([prediction]) == {
        "identity_collision_count": 0.0,
        "runtime_benchmark_roundtrip": 1.0,
        "citation_provenance_violation_count": 0.0,
        "reranker_lineage_violation_count": 0.0,
        "missing_execution_slot_answer_count": 0.0,
    }
