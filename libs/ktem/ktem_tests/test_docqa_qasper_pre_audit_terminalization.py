from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.execution import ABSTAIN_MESSAGE, execute_controller_turn
from ktem.docqa.query_planning import build_query_plan
from ktem.docqa.terminal_semantic_commit import terminal_commit_projection_present
from ktem.reasoning.mara_qasper_candidate import (
    QASPER_CANDIDATE_INPUT_TOKEN_BUDGET,
    generate_qasper_typed_candidate,
)
from ktem.reasoning.mara_semantic_proposition_verifier import (
    build_semantic_proposition_verifier,
)

QUESTION = "Did the authors compare cross-lingual and single-language evaluation?"
EVIDENCE = "We compared cross-lingual and single-language evaluation."
EVIDENCE_2 = "The comparison included single-language evaluation."


class _ProviderFailureLLM:
    model_name = "semantic-test-model"

    def __init__(self, message: str) -> None:
        self.message = message
        self.calls = 0

    def __call__(self, _messages: Any, **_kwargs: Any) -> Any:
        self.calls += 1
        raise RuntimeError(self.message)


class _ParseFailureLLM:
    model_name = "semantic-test-model"

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, _messages: Any, **_kwargs: Any) -> Any:
        self.calls += 1
        return SimpleNamespace(text="not-json")


class _BudgetFailureLLM:
    model_name = "semantic-test-model"

    def __init__(self, input_token_budget: int) -> None:
        self.input_token_budget = input_token_budget
        self.calls = 0

    def get_num_tokens_from_messages(self, _messages: Any) -> int:
        return self.input_token_budget + 1

    def get_num_tokens(self, _text: str) -> int:
        return 0

    def __call__(self, _messages: Any, **_kwargs: Any) -> Any:
        self.calls += 1
        raise AssertionError("budget failure must stop before provider invocation")


class _CandidateLLM:
    model_name = "candidate-test-model"

    def __init__(self, candidate: str) -> None:
        self.candidate = candidate

    def __call__(self, _messages: Any, **_kwargs: Any) -> Any:
        return SimpleNamespace(
            text=json.dumps({"candidate": self.candidate}),
            finish_reason="stop",
        )


def _candidate_generator(candidate: str) -> Any:
    llm = _CandidateLLM(candidate)

    def generate(request: Any, _decision: Any, bundle: Any) -> str:
        return generate_qasper_typed_candidate(
            SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm)),
            request,
            bundle,
        )

    return generate


def _request() -> DocQARequest:
    return DocQARequest(
        prompt=QUESTION,
        retrieval_query=QUESTION,
        task_type="boolean",
        verification_mode="strict",
        verification_domain="qasper",
        route_policy="doc",
        allowed_routes=["doc_text"],
        selected_file_ids=["paper"],
        query_plan=build_query_plan(
            QUESTION,
            answer_type="boolean",
            verification_domain="qasper",
        ),
        origin="benchmark",
        generation_seed=17,
    )


def _retrieve_calls() -> tuple[list[tuple[str, int]], Any]:
    calls: list[tuple[str, int]] = []

    def retrieve(request: DocQARequest, decision: Any) -> dict[str, Any]:
        calls.append((decision.legacy_route, request.retrieval_round_id))
        return {
            "evidence": [
                {
                    "evidence_id": "authority-left",
                    "source_id": "paper",
                    "section_id": "experiments",
                    "text": EVIDENCE,
                },
                {
                    "evidence_id": "authority-right",
                    "source_id": "paper",
                    "section_id": "experiments",
                    "text": EVIDENCE_2,
                },
            ]
        }

    return calls, retrieve


@pytest.mark.parametrize("candidate", ["yes", "no", "unanswerable"])
@pytest.mark.parametrize(
    ("llm_factory", "failure_reason"),
    [
        (
            lambda: _ProviderFailureLLM("provider unavailable"),
            "provider_call_failed",
        ),
        (lambda: _ParseFailureLLM(), "invalid_model_json"),
    ],
    ids=["provider_failure", "parse_failure"],
)
def test_qasper_pre_audit_failure_is_terminal_and_does_not_recover(
    llm_factory: Any,
    failure_reason: str,
    candidate: str,
) -> None:
    llm = llm_factory()
    verifier = build_semantic_proposition_verifier(
        SimpleNamespace(
            answering_pipeline=SimpleNamespace(llm=llm),
            semantic_proposition_debug_trace=True,
        )
    )
    assert verifier is not None
    retrieve_calls, retrieve = _retrieve_calls()

    result = execute_controller_turn(
        _request(),
        retrieve=retrieve,
        generate=_candidate_generator(candidate),
        proposition_verifier=verifier,
    )

    trace = result.evidence_bundle.metadata["semantic_proposition_verifier"]
    assert retrieve_calls == [("doc_text", 1), ("doc_text", 1)]
    assert result.answer == ABSTAIN_MESSAGE
    assert result.verify_decision.status == "execution_failed"
    assert result.verify_decision.action == "error"
    assert result.verify_decision.reason == failure_reason
    assert result.verify_decision.candidate_label == candidate
    assert result.verify_decision.verifier_input_candidate == candidate
    assert result.verify_decision.verifier_candidate_status == "pre_audit_failed"
    assert result.verify_decision.unknown_claims == []
    assert result.verify_decision.claim_results == []
    assert result.guardrail_decision.status == "execution_failed"
    assert result.guardrail_decision.action == "error"
    assert result.engine_terminal_answer == "unanswerable"
    assert result.engine_terminal_commit["outcome"] == "execution_failed"
    assert result.engine_terminal_commit["semantic_answer"] == "unanswerable"
    assert result.engine_terminal_commit["presentation_answer"] == ABSTAIN_MESSAGE
    assert result.engine_terminal_commit["authoritative_evidence"] == []
    assert result.engine_terminal_commit["citations"] == []
    assert terminal_commit_projection_present(result.engine_terminal_commit)
    assert trace["candidate_verification_status"] == "pre_audit_failed"
    assert trace["audit_status"] == "not_started"
    assert trace["audit_model_call_count"] == 0
    assert trace["candidate_verification_audit"]["status"] == "not_started"
    assert trace["candidate_verification_audit"]["classification"] == (
        "pre_audit_failed"
    )
    assert trace["unknown"] is False
    assert not any(
        event.get("stage")
        in {
            "critic",
            "focused_retrieval",
            "evidence_rebind",
            "targeted_retrieval",
            "reverify",
            "verifier_recovery",
        }
        for event in result.controller_trace
    )


def test_qasper_pre_audit_failure_keeps_candidate_trace_reason_on_cached_retry() -> (
    None
):
    llm = _ProviderFailureLLM("provider unavailable")
    verifier = build_semantic_proposition_verifier(
        SimpleNamespace(
            answering_pipeline=SimpleNamespace(llm=llm),
            semantic_proposition_debug_trace=True,
        )
    )
    assert verifier is not None
    retrieve_calls, retrieve = _retrieve_calls()

    result = execute_controller_turn(
        _request(),
        retrieve=retrieve,
        generate=_candidate_generator("yes"),
        proposition_verifier=verifier,
    )

    trace = result.evidence_bundle.metadata["semantic_proposition_verifier"]
    assert result.verify_decision.status == "execution_failed"
    assert result.engine_terminal_commit["outcome"] == "execution_failed"
    assert retrieve_calls == [("doc_text", 1), ("doc_text", 1)]
    assert llm.calls == 1
    assert trace["status"] == "failed"
    assert trace["candidate_verification_status"] == "pre_audit_failed"
    assert trace["audit_status"] == "not_started"
    assert trace["audit_model_call_count"] == 0


@pytest.mark.parametrize(
    ("llm_factory", "failure_reason"),
    [
        (
            lambda: _ProviderFailureLLM("candidate provider unavailable"),
            "provider_call_failed",
        ),
        (lambda: _ParseFailureLLM(), "json_decode_error"),
        (
            lambda: _BudgetFailureLLM(QASPER_CANDIDATE_INPUT_TOKEN_BUDGET),
            "candidate_input_budget_exceeded",
        ),
    ],
    ids=[
        "candidate_provider_failure",
        "candidate_parse_failure",
        "candidate_budget_failure",
    ],
)
def test_qasper_candidate_generation_failure_terminalizes_before_verifier(
    llm_factory: Any,
    failure_reason: str,
) -> None:
    llm = llm_factory()
    retrieve_calls, retrieve = _retrieve_calls()
    verifier_calls: list[str] = []

    def forbidden_verifier(*_args: Any, **_kwargs: Any) -> Any:
        verifier_calls.append("called")
        raise AssertionError("candidate-generation failure must precede verification")

    def generate(_request: Any, _decision: Any, bundle: Any) -> str:
        return generate_qasper_typed_candidate(
            SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm)),
            _request,
            bundle,
        )

    result = execute_controller_turn(
        _request(),
        retrieve=retrieve,
        generate=generate,
        proposition_verifier=forbidden_verifier,
    )

    generation = result.evidence_bundle.metadata["qasper_candidate_generation"]
    assert retrieve_calls == [("doc_text", 1), ("doc_text", 1)]
    assert result.answer == ABSTAIN_MESSAGE
    assert result.verify_decision.status == "execution_failed"
    assert result.verify_decision.action == "error"
    assert result.verify_decision.reason == failure_reason
    assert result.verify_decision.verifier_candidate_status == "pre_audit_failed"
    assert result.verify_decision.unknown_claims == []
    assert result.verify_decision.claim_results == []
    assert result.guardrail_decision.status == "execution_failed"
    assert result.guardrail_decision.action == "error"
    assert result.engine_terminal_answer == "unanswerable"
    assert result.engine_terminal_commit["outcome"] == "execution_failed"
    assert result.engine_terminal_commit["semantic_answer"] == "unanswerable"
    assert result.engine_terminal_commit["presentation_answer"] == ABSTAIN_MESSAGE
    assert result.engine_terminal_commit["authoritative_evidence"] == []
    assert result.engine_terminal_commit["citations"] == []
    assert terminal_commit_projection_present(result.engine_terminal_commit)
    assert verifier_calls == []
    assert "semantic_proposition_verifier" not in result.evidence_bundle.metadata
    assert generation["status"] == "failed"
    assert generation["failure_reason"] == failure_reason
    terminal_events = [
        event
        for event in result.controller_trace
        if event.get("stage") == "terminal_outcome"
    ]
    assert terminal_events
    assert terminal_events[-1]["candidate_verification_status"] == ("pre_audit_failed")
    assert terminal_events[-1]["audit_status"] == "not_started"
    assert terminal_events[-1]["audit_model_call_count"] == 0
    assert not any(
        event.get("stage")
        in {
            "critic",
            "focused_retrieval",
            "evidence_rebind",
            "targeted_retrieval",
            "reverify",
            "verifier_recovery",
        }
        for event in result.controller_trace
    )
