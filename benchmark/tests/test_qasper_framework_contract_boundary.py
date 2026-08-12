from __future__ import annotations

from copy import deepcopy
from typing import Any

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.execution import execute_controller_turn

from benchmark.answer_finalizer import finalize_prediction_answer
from benchmark.contract_invariant_metrics import contract_invariant_summary
from benchmark.qasper_contract_invariants import qasper_contract_metric_values
from benchmark.task_answer_contracts import (
    apply_task_answer_contract,
    synchronize_terminal_answer_state,
)


def _runtime_prediction() -> dict:
    question = "Did the authors release source code?"
    evidence = {
        "evidence_id": "release",
        "source_id": "paper",
        "section_id": "methods",
        "text": "We released the source code with the paper.",
    }
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
        retrieve=lambda *_args: {"evidence": [evidence]},
        generate=lambda *_args: "Yes. We released the source code.",
    )
    prediction = {
        **execution.as_dict(),
        "example_id": "release-example",
        "question": question,
        "answer_type": "boolean",
        "predicted_answer": execution.answer,
        "route": "text_rag",
        "gold_answers": ["yes"],
        "gold_evidence": ["release"],
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


def _runtime_abstention_prediction() -> dict:
    question = "Did the authors release source code?"
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
        retrieve=lambda *_args: {"evidence": []},
        generate=lambda *_args: (_ for _ in ()).throw(
            AssertionError("generation must not run without evidence")
        ),
    )
    prediction = {
        **execution.as_dict(),
        "example_id": "safe-abstention-example",
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
        dataset_name="qasper_typed",
        mode="scoring_adapter_v1",
    )
    return prediction


def _runtime_generated_abstention_prediction() -> dict:
    question = "Do the authors conduct experiments on the tasks mentioned?"
    evidence = {
        "evidence_id": "experiment",
        "source_id": "paper",
        "text": (
            "Sentence pairs are useful challenges for machine translation.\n\n"
            "## Current state of the art\n"
            "For instance, the sentence is translated by Google Translate, "
            "Bing Translate, and Yandex. In fact, I have been unable to "
            "construct any English sentence that those systems translate "
            "using the feminine plural pronoun."
        ),
    }
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
        retrieve=lambda *_args: {"evidence": [evidence]},
        generate=lambda *_args: "unanswerable The context does not mention experiments.",
    )
    prediction = {
        **execution.as_dict(),
        "example_id": "1dc2da5078a7e5ea82ccd1c90d81999a922bc9bf",
        "question": question,
        "answer_type": "boolean",
        "predicted_answer": execution.answer,
        "route": "text_rag",
        "gold_answers": ["yes"],
        "gold_evidence": ["experiment"],
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


def _runtime_free_text_prediction() -> dict:
    question = "What background knowledge does the method leverage?"
    answer = "The method leverages labeled features and class distribution."
    evidence = {
        "evidence_id": "background",
        "source_id": "paper",
        "text": answer,
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
        "example_id": "free-text-punctuation",
        "question": question,
        "answer_type": "evidence_qa",
        "predicted_answer": execution.answer,
        "route": "text_rag",
        "gold_answers": [answer],
        "gold_evidence": ["background"],
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


def test_complete_runtime_authority_is_a_zero_llm_pass_through() -> None:
    prediction = _runtime_prediction()
    immutable = {
        key: deepcopy(prediction[key])
        for key in (
            "engine_terminal_answer",
            "engine_terminal_state",
            "engine_verify_decision",
            "engine_terminal_projection_hash",
        )
    }

    changed = apply_task_answer_contract(
        prediction,
        dataset_name="qasper_typed",
        llm_factory=lambda: (_ for _ in ()).throw(
            AssertionError("QASPER adapter must not create a post-engine LLM")
        ),
    )
    synchronized = synchronize_terminal_answer_state(prediction)

    assert changed is False
    assert synchronized is True
    assert prediction["answer_for_scoring"] == "yes"
    assert prediction["predicted_answer"] == "yes"
    assert prediction["contract_action"] == "pass_through"
    assert prediction["contract_semantic_rewrite"] is False
    assert prediction["post_engine_answerability_llm_call_count"] == 0
    assert prediction["task_answer_contract"]["status"] == "audited"
    for key, value in immutable.items():
        assert prediction[key] == value
    summary = contract_invariant_summary([prediction])
    assert summary["contract_semantic_rewrite_count"] == 0.0
    assert summary["qasper_post_engine_answerability_llm_call_count"] == 0.0
    assert summary["qasper_runtime_authority_missing_count"] == 0.0


def test_runtime_authority_is_used_directly_for_terminal_citation() -> None:
    prediction = _runtime_generated_abstention_prediction()

    apply_task_answer_contract(
        prediction,
        dataset_name="qasper_contract_smoke",
        llm_factory=lambda: (_ for _ in ()).throw(AssertionError("no LLM")),
    )
    synchronize_terminal_answer_state(prediction)

    assert prediction["engine_terminal_answer"] == "yes"
    assert prediction["contract_action"] == "pass_through"
    assert (
        prediction["evidence_metadata"]["qasper_answerability"]["contract_action"]
        == "pass_through"
    )
    [citation] = prediction["structured_citations"]
    assert citation["evidence_id"] == (
        prediction["engine_verify_decision"]["authoritative_evidence_id"]
    )
    [emitted] = prediction["evidence_metadata"]["emitted_citation_evidence"]
    assert identity_of(emitted).key == citation["evidence_id"]


def test_scoring_punctuation_normalization_is_not_a_semantic_rewrite() -> None:
    prediction = _runtime_free_text_prediction()

    apply_task_answer_contract(
        prediction,
        dataset_name="qasper_contract_smoke",
        llm_factory=lambda: (_ for _ in ()).throw(AssertionError("no LLM")),
    )
    synchronize_terminal_answer_state(prediction)

    assert prediction["engine_terminal_answer"].endswith(".")
    assert not prediction["answer_for_scoring"].endswith(".")
    assert prediction["predicted_answer"] == prediction["engine_terminal_answer"]
    assert prediction["terminal_answer_state"]["answer"] == (
        prediction["engine_terminal_answer"]
    )
    assert prediction["contract_action"] == "pass_through"
    assert prediction["contract_semantic_rewrite"] is False


def test_required_authority_coverage_excludes_non_applicable_rows() -> None:
    answerable = _runtime_prediction()
    abstention = _runtime_abstention_prediction()
    free_text = _runtime_free_text_prediction()
    for prediction in (answerable, abstention, free_text):
        apply_task_answer_contract(
            prediction,
            dataset_name="qasper_contract_smoke",
            llm_factory=lambda: (_ for _ in ()).throw(AssertionError("no LLM")),
        )

    summary = contract_invariant_summary([answerable, abstention, free_text])

    assert summary["qasper_required_verification_applicable_count"] == 1.0
    assert summary["verifier_required_evidence_coverage"] == 1.0


def test_safe_runtime_abstention_requires_projection_but_not_polarity_authority() -> None:
    prediction = _runtime_abstention_prediction()

    apply_task_answer_contract(
        prediction,
        dataset_name="qasper_typed",
        llm_factory=lambda: (_ for _ in ()).throw(AssertionError("no LLM")),
    )

    trace = prediction["evidence_metadata"]["qasper_answerability"]
    assert prediction["predicted_answer"] == "unanswerable"
    assert prediction["contract_action"] == "pass_through"
    assert trace["runtime_projection_present"] is True
    assert trace["runtime_boolean_authority_applicable"] is False
    assert trace["reason"] == "runtime_safe_abstention"
    summary = contract_invariant_summary([prediction])
    assert summary["qasper_runtime_authority_missing_count"] == 0.0
    assert summary["qasper_required_verification_applicable_count"] == 0.0


def test_missing_runtime_projection_is_a_hard_violation_without_llm_reanswer() -> None:
    prediction: dict[str, Any] = {
        "question": "Did the authors release source code?",
        "answer_type": "boolean",
        "predicted_answer": "yes",
        "answer_for_scoring": "yes",
        "evidence_metadata": {},
        "evidence_bundle": {},
    }

    apply_task_answer_contract(
        prediction,
        dataset_name="qasper_typed",
        llm_factory=lambda: (_ for _ in ()).throw(
            AssertionError("missing authority must not trigger benchmark re-answering")
        ),
    )

    assert prediction["predicted_answer"] == "yes"
    assert prediction["contract_action"] == "hard_violation_missing_runtime_authority"
    assert prediction["task_answer_contract"]["status"] == "violation"
    assert prediction["post_engine_answerability_llm_call_count"] == 0
    summary = contract_invariant_summary([prediction])
    assert summary["qasper_runtime_authority_missing_count"] == 1.0


def test_tampered_runtime_projection_is_a_hard_violation() -> None:
    prediction = _runtime_prediction()
    prediction["engine_terminal_state"]["answer"] = "no"

    apply_task_answer_contract(
        prediction,
        dataset_name="qasper_typed",
        llm_factory=lambda: (_ for _ in ()).throw(AssertionError("no LLM")),
    )

    assert prediction["contract_action"] == ("hard_violation_missing_runtime_authority")
    assert (
        prediction["evidence_metadata"]["qasper_answerability"][
            "runtime_projection_present"
        ]
        is False
    )


def test_adapter_detects_but_never_hides_semantic_label_rewrite() -> None:
    prediction = _runtime_prediction()
    prediction["predicted_answer"] = "no"
    prediction["answer_for_scoring"] = "no"

    apply_task_answer_contract(
        prediction,
        dataset_name="qasper_typed",
        llm_factory=lambda: (_ for _ in ()).throw(AssertionError("no LLM")),
    )

    assert prediction["predicted_answer"] == "no"
    assert prediction["engine_terminal_answer"] == "yes"
    assert prediction["contract_action"] == "hard_violation_semantic_rewrite"
    assert prediction["contract_semantic_rewrite"] is True
    assert (
        contract_invariant_summary([prediction])["contract_semantic_rewrite_count"]
        == 1.0
    )


def test_ref_mismatch_counts_even_when_repair_cleared_raw_verdict() -> None:
    prediction = {
        "example_id": "d274",
        "answer_type": "boolean",
        "predicted_answer": "unanswerable",
        "answer_for_scoring": "unanswerable",
        "gold_answers": ["yes"],
    }
    metadata = {
        "qasper_answerability": {
            "reason": "evidence_ref_quote_mismatch",
            "quote_ref_validation_status": "evidence_ref_quote_mismatch",
            "raw_verifier_verdict": "",
            "final_post_contract_answer": "unanswerable",
            "verifier_required_slot_ids": "support:boolean_proposition",
            "verifier_required_evidence_ids": "evidence:paper:support",
            "verifier_required_evidence_coverage": "1.000000",
        }
    }

    metrics = qasper_contract_metric_values(
        prediction,
        metadata,
        cited=[],
        contract_items=[],
    )

    assert metrics["qasper_complete_to_unanswerable_ref_mismatch_count"] == 0.0
    assert metrics["qasper_quote_validation_ref_mismatch_count"] == 1.0
