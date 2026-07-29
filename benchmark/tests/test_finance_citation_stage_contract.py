from __future__ import annotations

from typing import Any

from ktem.docqa.evidence_identity import identity_of

from benchmark.answer_finalizer import finalize_prediction_answer
from benchmark.contract_gate_metrics import prediction_gate_metrics


def _prediction(answer: str) -> dict[str, Any]:
    cell = {
        "source_id": "report",
        "page_label": "30",
        "table_id": "cash-flow",
        "cell_id": "capex-2021",
        "evidence_level": "cell",
        "row_label": "Capital expenditure",
        "column_label": "2021",
        "period": "2021",
        "value": "-4625",
        "text": "Capital expenditure 2021 (4,625) million",
    }
    citation_id = identity_of(cell).key
    return {
        "predicted_answer": answer,
        "answer_type": "numeric",
        "gold_answers": ["$4,625 million"],
        "gold_evidence": [{"source_id": "report", "page_label": "30"}],
        "predicted_sources": ["report#page:30"],
        "evidence_bundle": {
            "items": [cell],
            "metadata": {
                "finance_numeric_trace": {
                    "calculation_verification": {
                        "valid": True,
                        "required_slot_ids": ["operand:capex"],
                        "verified_required_slot_ids": ["operand:capex"],
                    },
                    "calculation_execution": {
                        "status": "ok",
                        "value": "-4625",
                        "citation_ids": [citation_id],
                    },
                }
            },
        },
    }


def test_execution_citation_does_not_count_as_answer_citation():
    prediction = _prediction("$4,625 million")
    metadata = {
        "execution_operand_evidence": prediction["evidence_bundle"]["items"],
        "query_plan": {"evidence_slots": []},
    }

    metrics = prediction_gate_metrics(
        prediction,
        metadata,
        candidates=prediction["evidence_bundle"]["items"],
        reranker_input=[],
        reranked=[],
        selected=[],
        generation_context=[],
    )

    assert metrics["execution_operand_provenance_coverage"] == 1.0
    assert metrics["final_answer_citation_emission"] == 0.0


def test_accepted_typed_answer_emits_operand_citations():
    prediction = _prediction("$4,625 million")

    finalize_prediction_answer(
        prediction,
        dataset_name="financebench",
        mode="scoring_adapter_v1",
    )

    metadata = prediction["evidence_metadata"]
    assert prediction["answer_status"] == "answered"
    assert metadata["execution_operand_evidence"]
    assert metadata["verified_claim_support_evidence"]
    assert metadata["emitted_citation_evidence"]


def test_abstention_keeps_diagnostic_execution_trace_only():
    prediction = _prediction(
        "MARA could not retrieve enough evidence to answer this question."
    )

    finalize_prediction_answer(
        prediction,
        dataset_name="financebench",
        mode="scoring_adapter_v1",
    )

    metadata = prediction["evidence_metadata"]
    assert prediction["answer_status"] == "abstained"
    assert metadata["execution_operand_evidence"]
    assert metadata["verified_claim_support_evidence"] == []
    assert metadata["emitted_citation_evidence"] == []
    assert prediction.get("structured_citations") in (None, [])


def test_correct_abstention_citation_gate_is_not_applicable():
    prediction = _prediction("unanswerable")
    prediction["gold_answers"] = ["unanswerable"]
    prediction["gold_evidence"] = []
    finalize_prediction_answer(
        prediction,
        dataset_name="financebench",
        mode="scoring_adapter_v1",
    )

    metrics = prediction_gate_metrics(
        prediction,
        prediction["evidence_metadata"],
        candidates=prediction["evidence_bundle"]["items"],
        reranker_input=[],
        reranked=[],
        selected=[],
        generation_context=[],
    )

    assert metrics["accepted_answer_count"] == 0.0
    assert metrics["final_answer_citation_emission"] is None


def test_claim_supported_citation_requires_accepted_final_answer():
    prediction = _prediction("unanswerable")
    finalize_prediction_answer(
        prediction,
        dataset_name="financebench",
        mode="scoring_adapter_v1",
    )

    assert prediction["evidence_metadata"]["verified_claim_support_evidence"] == []
    assert prediction["evidence_metadata"]["emitted_citation_evidence"] == []
