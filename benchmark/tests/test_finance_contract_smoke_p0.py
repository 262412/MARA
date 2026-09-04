from __future__ import annotations

from benchmark.answer_finalizer import finalize_prediction_answer
from benchmark.contract_gate_metrics import prediction_gate_metrics
from benchmark.source_join_metrics import source_join_metrics


def test_mara_refusal_scores_as_unanswerable():
    refusal = "MARA could not retrieve enough evidence to answer this question."
    prediction = {
        "predicted_answer": refusal,
        "gold_answers": ["unanswerable"],
        "guardrail_decision": {"action": "abstain"},
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="financebench",
        mode="product",
    )

    assert prediction["answer_for_user"] == refusal
    assert prediction["answer_for_scoring"] == "unanswerable"
    assert prediction["answer_status"] == "abstained"


def test_expected_abstention_does_not_require_calculation_execution():
    prediction = {
        "predicted_answer": "unanswerable",
        "answer_for_scoring": "unanswerable",
        "gold_answers": ["unanswerable"],
        "answer_status": "abstained",
        "gold_evidence": [],
    }
    metadata = {
        "query_plan": {
            "constraints": {
                "verification_domain": "finance",
                "finance_formula_status": "supported",
            },
            "evidence_slots": [
                {
                    "slot_id": "operand:operating_income:2099",
                    "role": "operand",
                    "required_for_execution": True,
                    "status": "missing",
                    "evidence_ids": [],
                }
            ],
        }
    }

    metrics = prediction_gate_metrics(
        prediction,
        metadata,
        candidates=[],
        reranker_input=[],
        reranked=[],
        selected=[],
        generation_context=[],
    )

    assert metrics["calculation_applicable"] == 0.0
    assert metrics["calculation_executed"] is None
    assert metrics["safe_abstention_applicable"] == 1.0
    assert metrics["safe_abstention_passed"] == 1.0
    assert metrics["citation_required"] == 0.0


def test_correct_abstention_does_not_require_verified_claim_support_or_citation():
    prediction = {
        "predicted_answer": "unanswerable",
        "answer_for_scoring": "unanswerable",
        "gold_answers": ["unanswerable"],
        "answer_status": "abstained",
        "gold_evidence": [],
    }
    metrics = prediction_gate_metrics(
        prediction,
        {"query_plan": {"evidence_slots": []}},
        candidates=[],
        reranker_input=[],
        reranked=[],
        selected=[],
        generation_context=[],
    )

    assert metrics["answerable_document_qa"] == 0.0
    assert metrics["citation_emission"] is None
    assert metrics["required_generation_context_nonempty"] is None


def test_source_crosswalk_metrics_are_separate_from_retrieval_coverage():
    prediction = {
        "source_identity_crosswalk": [
            {
                "canonical_dataset_id": "runtime-report",
                "aliases": ["gold-report"],
            }
        ],
        "gold_source_ids": ["gold-report"],
        "gold_evidence": [
            {
                "source_id": "gold-report",
                "page_label": "59",
            }
        ],
        "document_ids": ["gold-report"],
    }

    metrics = source_join_metrics(prediction, candidates=[])

    assert metrics["gold_source_alias_resolution_rate"] == 1.0
    assert metrics["gold_page_alias_resolution_rate"] == 1.0
    assert metrics["gold_source_page_crosswalk_rate"] == 1.0
    assert metrics["retrieved_gold_source_page_coverage"] == 0.0
