from __future__ import annotations

from benchmark.contract_gate_metrics import prediction_gate_metrics


def _prediction(*, route: str, role: str) -> dict[str, object]:
    return {
        "route": route,
        "route_id": route,
        "benchmark_role": role,
        "predicted_answer": "42",
        "answer_for_scoring": "42",
        "answer_status": "answered",
        "gold_answers": ["42"],
        "gold_evidence": [{"source_id": "report", "page_label": "52"}],
    }


def _metrics(prediction: dict[str, object]) -> dict[str, float | None]:
    return prediction_gate_metrics(
        prediction,
        {},
        candidates=[],
        reranker_input=[],
        reranked=[],
        selected=[],
        generation_context=[],
    )


def test_direct_diagnostic_route_does_not_apply_citation_or_evidence_stage_gates():
    metrics = _metrics(_prediction(route="direct_answer", role="diagnostic"))

    assert metrics["citation_required"] == 0.0
    assert metrics["citation_emission"] is None
    assert metrics["accepted_answer_citation_emission"] is None
    assert metrics["final_answer_citation_emission"] is None
    assert metrics["answerable_document_qa"] == 0.0
    assert metrics["evidence_stages_recorded"] is None
    assert metrics["required_evidence_stages_nonempty"] is None


def test_qa_quality_retrieval_route_keeps_citation_and_evidence_stage_gates_strict():
    metrics = _metrics(_prediction(route="text_rag", role="qa_quality"))

    assert metrics["citation_required"] == 1.0
    assert metrics["citation_emission"] == 0.0
    assert metrics["accepted_answer_citation_emission"] == 0.0
    assert metrics["final_answer_citation_emission"] == 0.0
    assert metrics["answerable_document_qa"] == 1.0
    assert metrics["evidence_stages_recorded"] == 0.0
    assert metrics["required_evidence_stages_nonempty"] == 0.0
