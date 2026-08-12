from __future__ import annotations

from copy import deepcopy
from typing import Any

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.execution import execute_controller_turn

from benchmark.answer_finalizer import finalize_prediction_answer
from benchmark.metrics import normalize_text
from benchmark.task_answer_contracts import (
    apply_task_answer_contract,
    synchronize_terminal_answer_state,
)


def _semantic(value: Any) -> str:
    """Compare complete free-text answers, ignoring presentation punctuation only."""

    return normalize_text(str(value or ""))


def _free_text_request(question: str) -> DocQARequest:
    return DocQARequest(
        prompt=question,
        retrieval_query=question,
        task_type="free_text",
        verification_domain="qasper",
        verification_mode="strict",
        route_policy="doc",
        allowed_routes=["doc_text"],
        selected_file_ids=["paper"],
        origin="benchmark",
    )


def _run_free_text_runtime(
    question: str,
    answer: str,
) -> tuple[Any, dict[str, Any]]:
    evidence = {
        "source_id": "paper",
        "span_id": "support",
        "text": answer,
    }
    execution = execute_controller_turn(
        _free_text_request(question),
        retrieve=lambda *_args: {"evidence": [evidence]},
        generate=lambda *_args: answer,
    )
    prediction: dict[str, Any] = {
        **execution.as_dict(),
        "question": question,
        "answer_type": "free_text",
        "predicted_answer": execution.answer,
        "route": "text_rag",
        "evidence_metadata": deepcopy(execution.evidence_bundle.metadata),
        "structured_citations": [],
        "predicted_citations": [],
    }
    return execution, prediction


def _commit_free_text_prediction(
    question: str,
    answer: str,
) -> tuple[Any, dict[str, Any]]:
    execution, prediction = _run_free_text_runtime(question, answer)
    finalize_prediction_answer(
        prediction,
        dataset_name="qasper_contract_smoke",
        mode="scoring_adapter_v1",
    )
    apply_task_answer_contract(
        prediction,
        dataset_name="qasper_contract_smoke",
        llm_factory=lambda: (_ for _ in ()).throw(
            AssertionError("free-text terminal commit must not re-answer with an LLM")
        ),
    )
    assert synchronize_terminal_answer_state(prediction)
    return execution, prediction


def test_free_text_terminal_commit_keeps_engine_contract_and_scoring_identity():
    answer = (
        "The method leverages labeled features. "
        "It also relies on class distribution."
    )
    _execution, prediction = _commit_free_text_prediction(
        "What background knowledge does the method leverage?",
        answer,
    )

    expected = _semantic(answer)
    committed_fields = (
        prediction["engine_terminal_answer"],
        prediction["predicted_answer"],
        prediction["answer_for_scoring"],
        prediction["post_contract_verification"]["answer"],
        prediction["terminal_answer_state"]["answer"],
        prediction["evidence_metadata"]["qasper_answerability"][
            "final_post_contract_answer"
        ],
    )
    assert all(_semantic(value) == expected for value in committed_fields)
    assert prediction["contract_action"] == "pass_through"
    assert prediction["contract_semantic_rewrite"] is False


def test_free_text_later_qualifier_and_quantifier_cannot_be_truncated():
    answer = (
        "The method improves retrieval. "
        "The improvement is statistically significant only for in-domain queries."
    )
    _execution, prediction = _commit_free_text_prediction(
        "What qualification applies to the retrieval improvement?",
        answer,
    )

    committed = _semantic(prediction["answer_for_scoring"])
    assert committed == _semantic(answer)
    assert "statistically significant only for indomain queries" in committed


def test_free_text_independent_answer_items_cannot_be_reduced_to_the_first():
    answer = (
        "The method uses labeled features. " "It also relies on class distribution."
    )
    _execution, prediction = _commit_free_text_prediction(
        "Which inputs does the method rely on?",
        answer,
    )

    committed = _semantic(prediction["answer_for_scoring"])
    assert committed == _semantic(answer)
    assert "labeled features" in committed
    assert "class distribution" in committed


def test_free_text_citation_rendering_is_not_a_semantic_rewrite():
    answer = "The method leverages labeled features."
    _execution, prediction = _run_free_text_runtime(
        "What background knowledge does the method leverage?",
        answer,
    )
    finalize_prediction_answer(
        prediction,
        dataset_name="qasper_contract_smoke",
        mode="scoring_adapter_v1",
    )
    citation = {"kind": "source", "source_id": "paper"}
    prediction["answer_for_user"] = f"{answer} paper#source"
    prediction["structured_citations"] = [citation]
    apply_task_answer_contract(
        prediction,
        dataset_name="qasper_contract_smoke",
        llm_factory=lambda: (_ for _ in ()).throw(
            AssertionError("citation presentation must not trigger re-answering")
        ),
    )
    assert synchronize_terminal_answer_state(prediction)

    assert prediction["answer_for_user"] == f"{answer} paper#source"
    assert prediction["answer_for_user"] != prediction["answer_for_scoring"]
    assert prediction["structured_citations"] == [citation]
    assert _semantic(prediction["engine_terminal_answer"]) == _semantic(
        prediction["answer_for_scoring"]
    )
    assert prediction["contract_action"] == "pass_through"
    assert prediction["contract_semantic_rewrite"] is False


def test_free_text_commit_is_reverified_before_terminal_projection(monkeypatch):
    from ktem.docqa import execution_results

    answer = (
        "The method leverages labeled features. "
        "It also relies on class distribution."
    )
    verified_inputs: list[str] = []
    projected_inputs: list[str] = []
    verify = execution_results._verify_decision
    project = execution_results.engine_terminal_projection

    def spy_verify(request, retrieve_decision, bundle, candidate):
        verified_inputs.append(str(candidate))
        return verify(request, retrieve_decision, bundle, candidate)

    def spy_project(candidate, *args, **kwargs):
        projected_inputs.append(str(candidate))
        return project(candidate, *args, **kwargs)

    monkeypatch.setattr(execution_results, "_verify_decision", spy_verify)
    monkeypatch.setattr(execution_results, "engine_terminal_projection", spy_project)

    execution, _prediction = _run_free_text_runtime(
        "What background knowledge does the method leverage?",
        answer,
    )

    assert verified_inputs
    assert projected_inputs
    committed = _semantic(execution.engine_terminal_answer)
    assert _semantic(verified_inputs[-1]) == committed
    assert _semantic(projected_inputs[-1]) == committed
    assert _semantic(execution.engine_terminal_state["answer"]) == committed
    assert _semantic(" ".join(execution.engine_verify_decision["claims"])) == committed
