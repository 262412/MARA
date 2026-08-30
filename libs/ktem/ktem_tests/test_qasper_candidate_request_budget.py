from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from typing import Any

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.query_planning import build_query_plan
from ktem.reasoning import mara_qasper_candidate_budget as candidate_budget
from ktem.reasoning.mara_qasper_candidate import (
    QASPER_CANDIDATE_INPUT_TOKEN_BUDGET,
    QASPER_CANDIDATE_MAX_MODEL_LEN,
    QASPER_CANDIDATE_MAX_TOKENS,
    QASPER_CANDIDATE_TOKEN_HEADROOM,
    estimate_qasper_candidate_input_tokens,
    generate_qasper_typed_candidate,
    qasper_candidate_response_format,
)
from ktem.reasoning.mara_qasper_candidate_evidence import (
    candidate_evidence_set_binding,
    candidate_selector_options,
)
from ktem.reasoning.mara_qasper_candidate_prompt import (
    _compact_candidate_evidence_set_binding,
    _compact_candidate_selector_options,
)
from ktem.reasoning.mara_qasper_semantic_pack import prepare_qasper_canonical_records
from ktem.reasoning.mara_semantic_proposition_packing import compact_json


class _ProviderTokenizer:
    """Expose the provider's message and text tokenization hooks."""

    def __init__(self, *, message_tokens: int, text_tokens: int) -> None:
        self.message_tokens = message_tokens
        self.text_tokens = text_tokens
        self.messages: Any = None
        self.schema_text = ""

    def get_num_tokens_from_messages(self, messages: Any) -> int:
        self.messages = messages
        return self.message_tokens

    def get_num_tokens(self, text: str) -> int:
        self.schema_text = text
        return self.text_tokens


class _BudgetLLM:
    model_name = "budget-test-model"

    def __init__(
        self, tokenizer: _ProviderTokenizer, *, prompt_tokens: int = 0
    ) -> None:
        self.tokenizer = tokenizer
        self.prompt_tokens = prompt_tokens
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    def get_num_tokens_from_messages(self, messages: Any) -> int:
        return self.tokenizer.get_num_tokens_from_messages(messages)

    def get_num_tokens(self, text: str) -> int:
        return self.tokenizer.get_num_tokens(text)

    def __call__(self, messages: Any, **kwargs: Any) -> Any:
        self.calls.append((messages, kwargs))
        return SimpleNamespace(
            text='{"candidate":"yes"}',
            prompt_tokens=self.prompt_tokens,
            completion_tokens=3,
            additional_kwargs={"finish_reason": "stop"},
        )


class _CompactingTokenizer(_ProviderTokenizer):
    def get_num_tokens_from_messages(self, messages: Any) -> int:
        self.messages = messages
        user_content = str(messages[-1].content)
        return (
            QASPER_CANDIDATE_INPUT_TOKEN_BUDGET + 1
            if "[E2]" in user_content
            else QASPER_CANDIDATE_INPUT_TOKEN_BUDGET
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
        trace_context={"trace_group_id": "budget-group"},
    )


def _bound_request(request: DocQARequest, *evidence_ids: str) -> DocQARequest:
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


def test_candidate_budget_reserves_output_and_explicit_headroom() -> None:
    assert QASPER_CANDIDATE_MAX_MODEL_LEN == 4096
    assert QASPER_CANDIDATE_MAX_TOKENS == 48
    assert QASPER_CANDIDATE_TOKEN_HEADROOM > 0
    assert QASPER_CANDIDATE_INPUT_TOKEN_BUDGET == (
        QASPER_CANDIDATE_MAX_MODEL_LEN
        - QASPER_CANDIDATE_MAX_TOKENS
        - QASPER_CANDIDATE_TOKEN_HEADROOM
    )


def test_candidate_budget_counts_actual_messages_and_response_schema() -> None:
    tokenizer = _ProviderTokenizer(message_tokens=123, text_tokens=17)
    llm = _BudgetLLM(tokenizer)
    messages = [
        SimpleNamespace(type="system", content="system"),
        SimpleNamespace(type="human", content="question"),
    ]
    schema = qasper_candidate_response_format()

    estimated = estimate_qasper_candidate_input_tokens(llm, messages, schema)

    assert estimated == 140
    assert tokenizer.messages is messages
    assert '"candidate"' in tokenizer.schema_text


def test_candidate_budget_uses_vllm_tokenize_for_messages_and_schema(
    monkeypatch,
) -> None:
    calls: list[dict[str, Any]] = []

    class _Response:
        def __init__(self, count: int) -> None:
            self.count = count

        def __enter__(self) -> "_Response":
            return self

        def __exit__(self, *args: Any) -> None:
            return None

        def read(self) -> bytes:
            return ('{"count":' + str(self.count) + "}").encode("ascii")

    def _urlopen(request: Any, timeout: float) -> _Response:
        import json

        calls.append(json.loads(request.data.decode("utf-8")))
        return _Response(101 if len(calls) == 1 else 17)

    monkeypatch.setattr(candidate_budget, "urlopen", _urlopen)
    llm = SimpleNamespace(
        model="Qwen/Qwen3-8B",
        base_url="http://127.0.0.1:8000/v1",
    )
    messages = [SimpleNamespace(type="system", content="system")]

    measurement = candidate_budget.candidate_input_token_measurement(
        llm,
        messages,
        qasper_candidate_response_format(),
    )

    assert measurement["estimated_input_tokens"] == 118
    assert measurement["message_tokens"] == 101
    assert measurement["schema_tokens"] == 17
    assert measurement["tokenizer_method"] == "/tokenize(messages)+/tokenize(schema)"
    assert measurement["tokenizer_exact"] is True
    assert calls[0]["messages"] == [{"role": "system", "content": "system"}]
    assert "response_format" in calls[1]["prompt"]


def test_candidate_evidence_serialization_keeps_spans_without_repeated_metadata() -> (
    None
):
    question = "Did the authors compare the systems?"
    text = "The authors compared the systems."
    record = {
        "label": "E1",
        "evidence_id": "e1",
        "text": text,
        "text_start": 0,
        "selectors": [
            {
                "selector_id": "E1:S1",
                "text": text,
                "span_start": 0,
                "span_end": len(text),
            }
        ],
    }

    [record] = prepare_qasper_canonical_records(question, [record])
    verbose_options = candidate_selector_options(record, question=question)
    compact_options = _compact_candidate_selector_options(record, question=question)
    verbose_binding = candidate_evidence_set_binding([record], question)
    compact_binding = _compact_candidate_evidence_set_binding(verbose_binding)

    expected_option = {
        "evidence_ref": "E1:S1",
        "span_start": 0,
        "span_end": len(text),
        "text": text,
        "allowed_proposition_slots": ["actor", "predicate", "object"],
        "relation_bearing": True,
        "candidate_relation_role": "polarity_evidence",
        "local_relation_state": "affirmative_assertion",
        "polarity_signal": "support",
    }
    assert {
        key: value
        for key, value in compact_options[0].items()
        if key != "proposition_slot_spans"
    } == expected_option
    assert set(compact_options[0]["proposition_slot_spans"]) == {
        "actor",
        "predicate",
        "object",
    }
    assert all(
        set(span) == {"evidence_ref", "span_start", "span_end", "text"}
        for span in compact_options[0]["proposition_slot_spans"].values()
    )
    assert "evidence_id" not in compact_options[0]
    assert "joint_slot_hint" not in compact_options[0]
    assert set(compact_binding) == {
        "binding_status",
        "selector_universe_status",
        "polarity_signal",
        "selected_refs",
        "support_refs",
        "contradiction_refs",
        "slot_refs",
        "slot_child_refs",
        "no_evidence_semantics",
    }
    assert len(compact_json(compact_options)) < len(compact_json(verbose_options))
    assert len(compact_json(compact_binding)) < len(compact_json(verbose_binding))


def test_candidate_generation_rejects_a_request_over_the_4096_boundary() -> None:
    tokenizer = _ProviderTokenizer(
        message_tokens=QASPER_CANDIDATE_INPUT_TOKEN_BUDGET + 1,
        text_tokens=0,
    )
    llm = _BudgetLLM(tokenizer)
    pipeline = SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    request = _bound_request(_request(), "evidence:paper:e1")
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

    assert generate_qasper_typed_candidate(pipeline, request, bundle) == ""
    assert llm.calls == []
    trace = bundle.metadata["qasper_candidate_generation"]
    assert trace["input_token_budget"] == QASPER_CANDIDATE_INPUT_TOKEN_BUDGET
    assert trace["estimated_input_tokens"] > trace["input_token_budget"]
    assert trace["failure_reason"] == "candidate_input_budget_exceeded"
    assert trace["evidence_count"] == 1


def test_candidate_generation_allows_exact_reserved_input_boundary() -> None:
    tokenizer = _ProviderTokenizer(
        message_tokens=QASPER_CANDIDATE_INPUT_TOKEN_BUDGET,
        text_tokens=0,
    )
    llm = _BudgetLLM(tokenizer)
    pipeline = SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    request = _bound_request(_request(), "evidence:paper:e1")
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
    assert len(llm.calls) == 1
    assert trace["estimated_input_tokens"] == QASPER_CANDIDATE_INPUT_TOKEN_BUDGET
    assert trace["status"] == "parsed"


def test_candidate_compaction_keeps_aligned_evidence_record() -> None:
    tokenizer = _CompactingTokenizer(message_tokens=0, text_tokens=0)
    llm = _BudgetLLM(tokenizer)
    pipeline = SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    request = _bound_request(_request(), "evidence:paper:e1")
    bundle = EvidenceBundle(
        route="text_rag",
        items=[
            {
                "evidence_id": "e1",
                "source_id": "paper",
                "text": "The authors compared the two systems.",
            },
            {
                "evidence_id": "e2",
                "source_id": "paper",
                "text": "An unrelated observation was recorded.",
            },
        ],
    )

    assert generate_qasper_typed_candidate(pipeline, request, bundle) == "yes"
    trace = bundle.metadata["qasper_candidate_generation"]
    assert trace["request_dropped_evidence_count"] == 1
    assert trace["evidence_count"] == 1
    request_projection = trace["candidate_request_projection_trace"]
    prompt_projection = trace["candidate_prompt_projection_trace"]
    assert prompt_projection["complete"] is True
    assert (
        prompt_projection["decision_count"] == prompt_projection["input_record_count"]
    )
    assert prompt_projection["attempt_count"] == len(prompt_projection["attempts"])
    assert request_projection["complete"] is True
    assert request_projection["input_record_count"] == trace["evidence_count"] == 1
    assert request_projection["selected_record_count"] == 1
    assert request_projection["decision_count"] == 1
    assert {decision["decision"] for decision in request_projection["decisions"]} == {
        "selected_for_model_request"
    }
    assert {attempt["decision"] for attempt in request_projection["attempts"]} == {
        "accepted"
    }
    candidate_message = trace["message_stack"][1]["content"]
    assert "[E1]" in candidate_message
    assert "evidence_id=evidence:paper:e1" not in candidate_message
    assert '"evidence_ref":"E1:S1"' in candidate_message
    assert (
        "[E2] evidence_id=evidence:paper:e2" not in trace["message_stack"][1]["content"]
    )
    assert llm.calls


def test_identified_provider_tokenizer_failure_is_terminal(monkeypatch) -> None:
    def _urlopen(*_args: Any, **_kwargs: Any) -> Any:
        raise OSError("tokenizer endpoint unavailable")

    monkeypatch.setattr(candidate_budget, "urlopen", _urlopen)

    class _ProviderFailureLLM:
        model = "Qwen/Qwen3-8B"
        base_url = "http://127.0.0.1:8000/v1"

        def __init__(self) -> None:
            self.calls = 0

        def __call__(self, *_args: Any, **_kwargs: Any) -> Any:
            self.calls += 1
            raise AssertionError("provider tokenizer failure must stop generation")

    llm = _ProviderFailureLLM()
    pipeline = SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    request = _bound_request(_request(), "evidence:paper:e1")
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

    assert generate_qasper_typed_candidate(pipeline, request, bundle) == ""
    trace = bundle.metadata["qasper_candidate_generation"]
    assert llm.calls == 0
    assert trace["failure_reason"] == "provider_tokenizer_failed"
    assert trace["tokenizer_failed"] is True
    assert trace["tokenizer_endpoint"] == "http://127.0.0.1:8000/tokenize"
    assert trace["tokenizer_failure_reason"] == "messages:OSError"
    assert trace["provider_failure_reason"] == "provider_tokenizer_failed"
    assert (
        "tokenizer_endpoint=http://127.0.0.1:8000/tokenize"
        in trace["provider_failure_detail"]
    )
    assert trace["attempts"] == [
        {
            "attempt_id": trace["attempt_id"],
            "status": "provider_failed",
            "failure_reason": "provider_tokenizer_failed",
            "failure_detail": trace["provider_failure_detail"],
        }
    ]
    assert trace["raw_response"] == ""
    assert trace["cleaned_response"] == ""
    assert trace["typed_candidate"] == ""
    assert trace["finish_reason"] == ""


def test_candidate_generation_traces_actual_input_tokens_schema_and_finish_reason() -> (
    None
):
    tokenizer = _ProviderTokenizer(message_tokens=100, text_tokens=17)
    llm = _BudgetLLM(tokenizer, prompt_tokens=117)
    pipeline = SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    request = _bound_request(_request(), "evidence:paper:e1")
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

    assert trace["estimated_input_tokens"] == 117
    assert trace["actual_input_tokens"] == 117
    assert trace["response_schema_digest"]
    assert trace["message_stack"] == [
        {"index": 0, "role": "system", "content": trace["message_stack"][0]["content"]},
        {"index": 1, "role": "user", "content": trace["message_stack"][1]["content"]},
    ]
    assert trace["finish_reason"] == "stop"
    assert trace["estimated_input_tokens"] <= trace["input_token_budget"]
