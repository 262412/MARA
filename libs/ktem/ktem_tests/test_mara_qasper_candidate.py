from __future__ import annotations

from dataclasses import replace
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


def _bind_required_slots(request: DocQARequest, *evidence_ids: str) -> DocQARequest:
    bound_ids = tuple(evidence_ids)
    request.query_plan = replace(
        request.query_plan,
        evidence_slots=tuple(
            replace(slot, evidence_ids=bound_ids)
            if slot.required_for_verification
            else slot
            for slot in request.query_plan.evidence_slots
        ),
    )
    return request


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

    assert (
        generate_qasper_typed_candidate(
            pipeline,
            _bind_required_slots(_request(), "evidence:paper:e1"),
            bundle,
        )
        == "yes"
    )

    trace = bundle.metadata["qasper_candidate_generation"]
    assert trace["contract_id"] == "qasper_typed_candidate_generation.v2"
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
    _bind_required_slots(request, "evidence:paper:e0")
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


def test_qasper_candidate_prompt_binds_typed_proposition_and_required_evidence_refs() -> (
    None
):
    llm = _RecordingLLM('{"candidate":"yes"}')
    pipeline = SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    request = _request()
    items = [
        {
            "evidence_id": "cross-lingual",
            "source_id": "paper",
            "section_id": "experiments",
            "text": "We evaluated transfer in the cross-lingual setting.",
        },
        {
            "evidence_id": "single-language",
            "source_id": "paper",
            "section_id": "experiments",
            "text": "The experiment included single-language baselines for comparison.",
        },
    ]
    request.prompt = (
        "Did the authors compare cross-lingual and single-language evaluation?"
    )
    request.controller_question = request.prompt
    request.retrieval_query = request.prompt
    request.query_plan = build_query_plan(
        request.prompt,
        answer_type="boolean",
        verification_domain="qasper",
    )
    request.query_plan = replace(
        request.query_plan,
        evidence_slots=tuple(
            replace(
                slot,
                evidence_ids=(
                    "evidence:paper:cross-lingual",
                    "evidence:paper:single-language",
                )
                if slot.slot_id == "support:proposition"
                else (
                    ("evidence:paper:cross-lingual",)
                    if slot.slot_id == "support:left_subject"
                    else ("evidence:paper:single-language",)
                ),
            )
            for slot in request.query_plan.evidence_slots
        ),
    )
    bundle = EvidenceBundle(route="text_rag", items=items)

    assert generate_qasper_typed_candidate(pipeline, request, bundle) == "yes"

    prompt = llm.calls[0][0][1].content
    assert "TYPED QUESTION PROPOSITION:" in prompt
    assert '"actor":"current_paper"' in prompt
    assert '"predicate":"compare"' in prompt
    assert '"object_surface":"cross-lingual and single-language evaluation"' in prompt
    assert '"quantifier":"none"' in prompt
    assert "REQUIRED VERIFICATION SLOTS:" in prompt
    assert "support:left_subject" in prompt
    assert "binding_status=bound" in prompt
    assert "evidence_ref=E1:S1" in prompt
    assert "evidence_ref=E2:S1" in prompt
    assert bundle.metadata["qasper_candidate_generation"]["typed_proposition"]


def test_qasper_candidate_parser_preserves_polarity_when_required_slot_is_unbound() -> (
    None
):
    llm = _RecordingLLM('{"candidate":"yes"}')
    pipeline = SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    request = _request()
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

    assert generate_qasper_typed_candidate(pipeline, request, bundle) == "yes"
    trace = bundle.metadata["qasper_candidate_generation"]
    assert all(slot["binding_status"] == "missing" for slot in trace["required_slots"])
    assert trace["failure_reason"] == ""
    assert trace["raw_candidate"] == "yes"
    assert trace["typed_candidate"] == "yes"
    assert trace["raw_candidate_identity_preserved"] is True
