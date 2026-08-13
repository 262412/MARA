from __future__ import annotations

from copy import deepcopy

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.execution import execute_controller_turn

from benchmark.answer_finalizer import finalize_prediction_answer
from benchmark.qasper_runtime_authority import runtime_typed_proposition_authority
from benchmark.task_answer_contracts import apply_task_answer_contract


def _prediction(*, exact: bool) -> dict:
    question = "How many participants did the authors recruit for the study?"
    answer = "The authors recruited 42 participants."
    evidence = {
        "evidence_id": "participants",
        "source_id": "paper",
        "section_id": "results",
        "text": (
            "We recruited 42 participants for the study."
            if exact
            else "The study discusses participant demographics and methods."
        ),
    }
    execution = execute_controller_turn(
        DocQARequest(
            prompt=question,
            retrieval_query=question,
            task_type="free_text",
            verification_domain="qasper",
            verification_mode="strict",
            route_policy="doc",
            allowed_routes=["doc_text"],
            selected_file_ids=["paper"],
            origin="benchmark",
        ),
        retrieve=lambda *_args: {"evidence": [evidence]},
        generate=lambda *_args: answer,
    )
    prediction = {
        **execution.as_dict(),
        "example_id": "typed-authority",
        "question": question,
        "answer_type": "evidence_qa" if exact else "unanswerable",
        "predicted_answer": execution.answer,
        "answer_for_user": execution.answer,
        "route": "text_rag",
        "gold_answers": [answer if exact else "unanswerable"],
        "evidence_metadata": deepcopy(execution.evidence_bundle.metadata),
        "structured_citations": [],
        "predicted_citations": [],
    }
    finalize_prediction_answer(
        prediction,
        dataset_name="qasper_typed",
        mode="scoring_adapter_v1",
    )
    return prediction


def test_benchmark_only_audits_complete_runtime_typed_authority() -> None:
    prediction = _prediction(exact=True)
    before = (
        prediction["engine_terminal_answer"],
        prediction["predicted_answer"],
        prediction["answer_for_scoring"],
    )

    assert runtime_typed_proposition_authority(prediction)["complete"] is True
    assert not apply_task_answer_contract(
        prediction,
        dataset_name="qasper_typed",
        llm_factory=lambda: (_ for _ in ()).throw(AssertionError("no LLM")),
    )

    assert (
        prediction["engine_terminal_answer"],
        prediction["predicted_answer"],
        prediction["answer_for_scoring"],
    ) == before
    trace = prediction["evidence_metadata"]["qasper_answerability"]
    assert trace["runtime_typed_authority_applicable"] is True
    assert trace["runtime_typed_authority_complete"] is True
    assert trace["runtime_typed_authority_state"] == "verified_support"
    assert trace["verifier_required_evidence_coverage"] == "1.000000"
    assert trace["verifier_missing_required_slot_ids"] == ""
    assert prediction["contract_action"] == "pass_through"


def test_tampered_authority_atom_is_reported_without_benchmark_repair() -> None:
    prediction = _prediction(exact=True)
    original_answer = prediction["engine_terminal_answer"]
    atom = prediction["engine_verify_decision"]["typed_authority"]["authority_atoms"][0]
    atom["evidence_ref"] = "tampered"

    audit = runtime_typed_proposition_authority(prediction)

    assert audit["complete"] is False
    assert audit["atom_status"] == "canonical_ref_identity_mismatch"
    assert audit["identity_status"] == "canonical_ref_identity_mismatch"
    assert audit["quote_grounding_status"] == "not_evaluated"
    assert prediction["engine_terminal_answer"] == original_answer


def test_quote_grounding_failure_is_distinct_from_identity_mismatch() -> None:
    prediction = _prediction(exact=True)
    atom = prediction["engine_verify_decision"]["typed_authority"]["authority_atoms"][0]
    atom["quote"] = "The evidence does not contain this quote."

    audit = runtime_typed_proposition_authority(prediction)

    assert audit["complete"] is False
    assert audit["atom_status"] == "quote_semantic_grounding_failure"
    assert audit["identity_status"] == "bound"
    assert audit["quote_grounding_status"] == "quote_semantic_grounding_failure"


def test_safe_missing_projection_contains_no_exact_claim_or_citation() -> None:
    prediction = _prediction(exact=False)
    audit = runtime_typed_proposition_authority(prediction)

    assert prediction["engine_terminal_answer"] == "unanswerable"
    assert audit["complete"] is True
    assert audit["state"] == "missing"
    decision = prediction["engine_verify_decision"]
    assert decision["verified_citations"] == []
    assert decision["authoritative_evidence_id"] == ""
    assert not any(
        result.get("authority_status") == "exact"
        for result in decision["claim_results"]
    )
