from __future__ import annotations

from copy import deepcopy

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.execution import execute_controller_turn

from benchmark.answer_finalizer import finalize_prediction_answer
from benchmark.contract_invariant_metrics import contract_invariant_summary
from benchmark.qasper_runtime_authority import runtime_boolean_authority
from benchmark.task_answer_contracts import (
    apply_task_answer_contract,
    synchronize_terminal_answer_state,
)


def _conflict_prediction() -> dict:
    question = "Across pages 1 and 2, did the authors release the code?"
    evidence = [
        {
            "evidence_id": "positive",
            "source_id": "paper",
            "page_label": "1",
            "section_id": "results",
            "text": "The authors released the code publicly with the paper.",
        },
        {
            "evidence_id": "negative",
            "source_id": "paper",
            "page_label": "2",
            "section_id": "results",
            "text": "The authors did not release the code for the final system.",
        },
    ]
    execution = execute_controller_turn(
        DocQARequest(
            prompt=question,
            retrieval_query=question,
            task_type="boolean",
            verification_domain="qasper",
            verification_mode="strict",
            route_policy="doc",
            allowed_routes=["doc_text"],
            selected_file_ids=["paper"],
            origin="benchmark",
        ),
        retrieve=lambda *_args: {"evidence": evidence},
        generate=lambda *_args: "yes",
    )
    prediction = {
        **execution.as_dict(),
        "example_id": "cross-page-conflict",
        "question": question,
        "answer_type": "boolean",
        "predicted_answer": execution.answer,
        "gold_answers": ["unanswerable"],
        "evidence_metadata": deepcopy(execution.evidence_bundle.metadata),
        "structured_citations": [],
        "predicted_citations": [],
    }
    finalize_prediction_answer(
        prediction,
        dataset_name="qasper_contract_smoke",
        mode="scoring_adapter_v1",
    )
    return prediction


def test_benchmark_passively_audits_complete_authoritative_conflict() -> None:
    prediction = _conflict_prediction()

    apply_task_answer_contract(
        prediction,
        dataset_name="qasper_contract_smoke",
        llm_factory=lambda: (_ for _ in ()).throw(AssertionError("no LLM")),
    )
    assert synchronize_terminal_answer_state(prediction)

    authority = runtime_boolean_authority(prediction)
    assert authority["complete"] is True
    assert authority["authority_kind"] == "authoritative_conflict"
    assert prediction["predicted_answer"] == "unanswerable"
    assert prediction["answer_for_scoring"] == "unanswerable"
    assert prediction["contract_action"] == "pass_through"
    assert prediction["contract_semantic_rewrite"] is False
    assert prediction["structured_citations"] == []
    assert prediction["predicted_citations"] == []

    trace = prediction["evidence_metadata"]["qasper_answerability"]
    assert trace["reason"] == "runtime_authoritative_conflict"
    assert trace["raw_verifier_verdict"] == "conflict_complete"
    assert trace["verifier_required_evidence_coverage"] == "1.000000"
    assert trace["verifier_missing_required_slot_ids"] == ""
    assert trace["quote_ref_validation_status"] == "bound"

    summary = contract_invariant_summary([prediction])
    assert summary["verifier_required_evidence_coverage"] == 1.0
    assert summary["qasper_required_slot_authority_empty_count"] == 0.0
    assert summary["qasper_required_slot_authority_missing_count"] == 0.0
    assert summary["qasper_quote_validation_ref_mismatch_count"] == 0.0
    assert summary["contract_semantic_rewrite_count"] == 0.0
    assert summary["engine_scored_semantic_label_mismatch_count"] == 0.0
    assert summary["answerable_false_abstention_count"] == 0.0
