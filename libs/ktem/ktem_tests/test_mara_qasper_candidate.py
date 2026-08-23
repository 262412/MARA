from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.query_planning import build_query_plan
from ktem.reasoning.mara_qasper_candidate import (
    generate_qasper_typed_candidate,
    parse_qasper_candidate,
)


class _RecordingLLM:
    model_name = "live-shaped-test-model"

    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    def __call__(self, messages: Any, **kwargs: Any) -> Any:
        self.calls.append((messages, kwargs))
        return SimpleNamespace(
            text=self.text,
            completion_tokens=7,
            additional_kwargs={"finish_reason": "stop"},
        )


def _request() -> DocQARequest:
    question = "Did the authors compare the two systems?"
    return DocQARequest(
        prompt=question,
        controller_question=question,
        retrieval_query=question,
        dataset_family="qasper",
        task_type="qasper_qa",
        answer_type="boolean",
        origin="benchmark",
        verification_domain="qasper",
        verification_mode="strict",
        query_plan=build_query_plan(
            question,
            answer_type="boolean",
            verification_domain="qasper",
        ),
        generation_seed=23,
        trace_context={
            "contract_id": "benchmark_transaction_identity.v1",
            "trace_group_id": "group-1",
        },
    )


def test_qasper_candidate_generator_records_full_model_boundary() -> None:
    llm = _RecordingLLM('{"candidate":"yes"}')
    pipeline = SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    bundle = EvidenceBundle(
        route="text_rag",
        items=[
            {
                "evidence_id": "e1",
                "source_id": "paper",
                "text": "The authors compared the two systems.",
            }
        ],
    )

    assert generate_qasper_typed_candidate(pipeline, _request(), bundle) == "yes"

    trace = bundle.metadata["qasper_candidate_generation"]
    assert trace["contract_id"] == "qasper_typed_candidate_generation.v1"
    assert trace["trace_group_id"] == "group-1"
    assert trace["effective_seed"] == 23
    assert trace["status"] == "parsed"
    assert trace["raw_response"] == '{"candidate":"yes"}'
    assert trace["cleaned_response"] == '{"candidate":"yes"}'
    assert trace["typed_candidate"] == "yes"
    assert trace["finish_reason"] == "stop"
    assert trace["message_stack"][0]["role"] == "system"
    assert trace["message_stack"][1]["role"] == "user"
    assert trace["input_digest"]
    assert trace["output_digest"]
    assert trace["attempts"][0]["attempt_id"] == trace["attempt_id"]
    assert llm.calls[0][1]["response_format"]["json_schema"]["strict"] is True


def test_qasper_candidate_parser_rejects_prose_and_extra_fields() -> None:
    assert parse_qasper_candidate("yes") == ("", "json_decode_error")
    assert parse_qasper_candidate('{"candidate":"yes","reason":"x"}') == (
        "",
        "candidate_schema_invalid",
    )


def test_qasper_candidate_generator_fits_large_evidence_to_model_budget() -> None:
    llm = _RecordingLLM('{"candidate":"yes"}')
    pipeline = SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    request = _request()
    request.max_context_length = 3000
    bundle = EvidenceBundle(
        route="text_rag",
        items=[
            {
                "evidence_id": f"e{index}",
                "source_id": "paper",
                "text": (f"Evidence item {index} establishes the comparison. " * 100),
            }
            for index in range(12)
        ],
    )

    assert generate_qasper_typed_candidate(pipeline, request, bundle) == "yes"

    trace = bundle.metadata["qasper_candidate_generation"]
    prompt = llm.calls[0][0][1].content
    assert trace["evidence_input_count"] == 12
    assert trace["evidence_estimated_input_tokens"] <= trace["evidence_token_budget"]
    assert trace["evidence_dropped_count"] or trace["evidence_truncated_count"]
    assert len(prompt) <= trace["prompt_char_limit"]
