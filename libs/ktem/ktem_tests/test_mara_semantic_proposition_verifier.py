from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.controller import RetrieveDecision
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.query_planning import build_query_plan
from ktem.docqa.verification import verify_decision
from ktem.reasoning import mara as mara_module
from ktem.reasoning.mara import MaraAgentPipeline
from ktem.reasoning.mara_semantic_proposition_packing import (
    SEMANTIC_PROPOSITION_VERIFIER_INPUT_TOKEN_BUDGET,
    SEMANTIC_PROPOSITION_VERIFIER_ITEM_CHARS,
)
from ktem.reasoning.mara_semantic_proposition_schema import (
    parse_semantic_proposition_result,
    semantic_proposition_response_format,
)
from ktem.reasoning.mara_semantic_proposition_verifier import (
    SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS,
    SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS,
    SEMANTIC_PROPOSITION_VERIFIER_MIN_MODEL_CONTEXT_TOKENS,
    build_semantic_proposition_verifier,
)

QUESTION = "Did the authors compare cross-lingual and single-language evaluation?"


class _RecordingLLM:
    model_name = "semantic-test-model"

    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    def __call__(self, messages: Any, **kwargs: Any) -> Any:
        self.calls.append((messages, kwargs))
        schema_name = (
            kwargs.get("response_format", {}).get("json_schema", {}).get("name")
        )
        return SimpleNamespace(
            text=(
                _audit_response()
                if schema_name == "semantic_entailment_audit"
                else self.response
            )
        )


class _FailingLLM:
    model_name = "semantic-test-model"

    def __init__(self, message: str) -> None:
        self.message = message
        self.call_count = 0

    def __call__(self, _messages: Any, **_kwargs: Any) -> Any:
        self.call_count += 1
        raise RuntimeError(self.message)


def _request() -> DocQARequest:
    return DocQARequest(
        prompt=QUESTION,
        retrieval_query=QUESTION,
        task_type="boolean",
        verification_mode="strict",
        verification_domain="general",
        route_policy="doc",
        allowed_routes=["doc_text"],
        selected_file_ids=["paper"],
        query_plan=build_query_plan(
            QUESTION,
            answer_type="boolean",
            verification_domain="general",
        ),
        generation_seed=17,
    )


def _items() -> list[dict[str, str]]:
    return [
        {
            "evidence_id": "cross-lingual",
            "source_id": "paper",
            "section_id": "experiments",
            "text": "Transfer was evaluated across two languages.",
        },
        {
            "evidence_id": "single-language",
            "source_id": "paper",
            "section_id": "experiments",
            "text": "The experiment included monolingual baselines for comparison.",
        },
    ]


def _model_response() -> str:
    return json.dumps(
        {
            "verdict": "yes",
            "support_mode": "evidence_set",
            "jointly_complete": True,
            "each_premise_required": True,
            "premises": [
                {
                    "evidence_ref": "E1",
                    "quote": "Transfer was evaluated across two languages.",
                    "proposition_fragment": "cross-language evaluation was performed",
                    "supports_slot_ids": [
                        "support:proposition",
                        "support:left_subject",
                    ],
                },
                {
                    "evidence_ref": "E2",
                    "quote": (
                        "The experiment included monolingual baselines for comparison."
                    ),
                    "proposition_fragment": (
                        "single-language baselines were included for comparison"
                    ),
                    "supports_slot_ids": [
                        "support:proposition",
                        "support:right_subject",
                    ],
                },
            ],
        }
    )


def _insufficient_response() -> str:
    return json.dumps(
        {
            "verdict": "insufficient_evidence",
            "support_mode": "evidence_set",
            "jointly_complete": False,
            "each_premise_required": False,
            "premises": [],
        }
    )


def _audit_response() -> str:
    return json.dumps(
        {
            "premise_checks": [
                {
                    "premise_ref": label,
                    "fragment_entailed": True,
                    "scope_consistent": True,
                }
                for label in ("P1", "P2")
            ],
            "jointly_entails": True,
            "each_premise_required": True,
            "contradiction_free": True,
        }
    )


def test_runtime_verifier_maps_labels_and_caches_one_evidence_signature() -> None:
    llm = _RecordingLLM(_model_response())
    verifier = build_semantic_proposition_verifier(
        SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    )
    assert verifier is not None
    request = _request()
    bundle = EvidenceBundle(route="doc_text", items=_items())

    first = verifier(request, QUESTION, "unanswerable", bundle)
    second = verifier(request, QUESTION, "yes", bundle)

    assert first == second
    assert first is not None
    assert len(llm.calls) == 2
    assert [value["evidence_id"] for value in first["premises"]] == [
        identity_of(item).key for item in _items()
    ]
    assert first["verifier"] == {
        "contract_id": "grounded_semantic_verifier.v1",
        "model": "semantic-test-model",
        "seed": 17,
    }
    messages, kwargs = llm.calls[0]
    assert "unanswerable" not in messages[1].content
    assert "at least one premise must explicitly anchor their action" in (
        messages[0].content
    )
    assert len(messages[1].content) <= SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS
    assert kwargs["temperature"] == 0
    assert kwargs["top_p"] == 1
    assert kwargs["response_format"]["json_schema"]["strict"] is True
    assert bundle.metadata["semantic_proposition_verifier"]["cache_hit"] is True
    assert (
        bundle.metadata["semantic_proposition_verifier"]["actual_model_call_count"] == 2
    )


def test_response_schema_uses_portable_subset_and_parser_rejects_duplicate_slots() -> (
    None
):
    response_format = semantic_proposition_response_format(
        ["E1", "E2"],
        ["support:proposition", "support:left_subject"],
    )
    assert "uniqueItems" not in json.dumps(response_format)

    response = json.loads(_model_response())
    response["premises"][0]["supports_slot_ids"] = [
        "support:proposition",
        "support:proposition",
    ]
    packed = [
        {"label": "E1", "evidence_id": "first"},
        {"label": "E2", "evidence_id": "second"},
    ]

    assert (
        parse_semantic_proposition_result(
            json.dumps(response),
            packed=packed,
            slot_ids={
                "support:proposition",
                "support:left_subject",
                "support:right_subject",
            },
            model="semantic-test-model",
            seed=17,
        )
        is None
    )


def test_runtime_verifier_honors_request_evidence_budget() -> None:
    llm = _RecordingLLM(_insufficient_response())
    verifier = build_semantic_proposition_verifier(
        SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    )
    assert verifier is not None
    request = _request()
    request.max_context_length = 2000
    items = [
        {
            "evidence_id": f"item-{index}",
            "source_id": "paper",
            "section_id": "experiments",
            "text": f"Evidence {index}: " + ("x" * 1900),
        }
        for index in range(8)
    ]
    bundle = EvidenceBundle(route="doc_text", items=items)

    verifier(request, QUESTION, "unanswerable", bundle)

    assert len(llm.calls) == 1
    messages, kwargs = llm.calls[0]
    trace = bundle.metadata["semantic_proposition_verifier"]
    assert kwargs["max_tokens"] == SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS
    assert SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS == 768
    assert (
        SEMANTIC_PROPOSITION_VERIFIER_INPUT_TOKEN_BUDGET
        + SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS
        <= SEMANTIC_PROPOSITION_VERIFIER_MIN_MODEL_CONTEXT_TOKENS
    )
    assert trace["evidence_item_char_limit"] == 2000
    assert trace["estimated_input_token_budget"] == (
        SEMANTIC_PROPOSITION_VERIFIER_INPUT_TOKEN_BUDGET
    )
    assert trace["estimated_input_tokens"] <= trace["estimated_input_token_budget"]
    assert trace["minimum_model_context_tokens"] == (
        SEMANTIC_PROPOSITION_VERIFIER_MIN_MODEL_CONTEXT_TOKENS
    )
    assert trace["dropped_evidence_count"] > 0
    assert trace["truncated_evidence_count"] > 0
    assert len(messages[1].content) <= SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS


def test_runtime_verifier_packs_query_plan_then_upstream_reranker_order() -> None:
    llm = _RecordingLLM(_insufficient_response())
    verifier = build_semantic_proposition_verifier(
        SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    )
    assert verifier is not None
    items = _items()
    ranked = [
        {"canonical_id": identity_of(items[1]).key},
        {"canonical_id": identity_of(items[0]).key},
    ]
    bundle = EvidenceBundle(
        route="doc_text",
        items=items,
        metadata={"candidate_ranked_evidence": ranked},
    )

    verifier(_request(), QUESTION, "unanswerable", bundle)

    prompt = llm.calls[0][0][1].content
    assert prompt.index(items[1]["text"]) < prompt.index(items[0]["text"])


@pytest.mark.parametrize(
    ("message", "reason"),
    [
        (
            "This model's maximum context length is 4096 tokens",
            "provider_context_length_exceeded",
        ),
        (
            'Grammar error: Unimplemented keys: ["uniqueItems"]',
            "provider_response_schema_unsupported",
        ),
    ],
)
def test_runtime_verifier_classifies_and_caches_provider_failures(
    message: str,
    reason: str,
) -> None:
    llm = _FailingLLM(message)
    verifier = build_semantic_proposition_verifier(
        SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    )
    assert verifier is not None
    bundle = EvidenceBundle(route="doc_text", items=_items())

    assert verifier(_request(), QUESTION, "unanswerable", bundle) is None
    assert verifier(_request(), QUESTION, "unanswerable", bundle) is None

    assert llm.call_count == 1
    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["status"] == "cached_failure"
    assert trace["reason"] == reason


def test_runtime_verifier_fails_closed_on_invalid_json() -> None:
    llm = _RecordingLLM("not-json")
    verifier = build_semantic_proposition_verifier(
        SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    )
    assert verifier is not None
    bundle = EvidenceBundle(route="doc_text", items=_items())

    assert verifier(_request(), QUESTION, "yes", bundle) is None
    assert bundle.metadata["semantic_proposition_verifier"]["status"] == "failed"
    assert bundle.metadata["semantic_proposition_verifier"]["reason"] == (
        "invalid_model_json"
    )


def test_runtime_verifier_preserves_full_canonical_chunk_window() -> None:
    tail_marker = "TAIL PREMISE MUST REMAIN VISIBLE"
    text = "x" * (SEMANTIC_PROPOSITION_VERIFIER_ITEM_CHARS - len(tail_marker))
    items = _items()
    items[0]["text"] = text + tail_marker
    llm = _RecordingLLM(_model_response())
    verifier = build_semantic_proposition_verifier(
        SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    )
    assert verifier is not None

    request = _request()
    request.max_context_length = 2000
    verifier(request, QUESTION, "yes", EvidenceBundle(route="doc_text", items=items))

    assert tail_marker in llm.calls[0][0][1].content


def test_runtime_verifier_accepts_distinct_spans_from_one_canonical_item() -> None:
    response = json.loads(_model_response())
    response["premises"][1]["evidence_ref"] = "E1"
    items = _items()
    items[0]["text"] = f"{items[0]['text']} {items[1]['text']}"
    llm = _RecordingLLM(json.dumps(response))
    verifier = build_semantic_proposition_verifier(
        SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    )
    assert verifier is not None

    result = verifier(
        _request(),
        QUESTION,
        "yes",
        EvidenceBundle(route="doc_text", items=[items[0]]),
    )

    assert result is not None
    assert len(llm.calls) == 2
    assert result["premises"][0]["evidence_id"] == result["premises"][1]["evidence_id"]


def test_runtime_verdict_commits_typed_authority_and_query_plan_bindings() -> None:
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
            "text": (
                "The same experiment included single-language baselines for comparison."
            ),
        },
    ]
    response = json.loads(_model_response())
    response["premises"][0]["quote"] = items[0]["text"]
    response["premises"][1]["quote"] = items[1]["text"]
    llm = _RecordingLLM(json.dumps(response))
    verifier = build_semantic_proposition_verifier(
        SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    )
    assert verifier is not None
    request = _request()
    bundle = EvidenceBundle(route="doc_text", items=items)

    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        bundle,
        "unanswerable",
        proposition_verifier=verifier,
    )

    assert decision.status == "supported"
    assert decision.boolean_authority_status == "verified_support"
    assert decision.typed_authority["state"] == "verified_support"
    assert bundle.metadata["semantic_proposition_verifier"]["status"] == "parsed"
    assert bundle.metadata["semantic_proposition_authority"]["status"] == "verified"
    required_slots = [
        slot
        for slot in request.query_plan.evidence_slots
        if slot.required_for_verification
    ]
    assert required_slots
    assert all(slot.status == "verified_support" for slot in required_slots)


def test_mara_route_injects_the_semantic_verifier(monkeypatch: Any) -> None:
    class StopExecution(RuntimeError):
        pass

    captured: dict[str, Any] = {}

    def fake_execute(_request: Any, **kwargs: Any) -> None:
        captured.update(kwargs)
        raise StopExecution

    monkeypatch.setattr(mara_module, "execute_controller_turn", fake_execute)
    pipeline = MaraAgentPipeline(retrievers=[])
    setattr(
        pipeline,
        "answering_pipeline",
        SimpleNamespace(llm=_RecordingLLM(_model_response())),
    )

    with pytest.raises(StopExecution):
        pipeline.execute_controller_route(
            QUESTION,
            "conv-1",
            [],
            {"modalities": ["text"]},
            {},
            {},
        )

    assert callable(captured["proposition_verifier"])
    assert "verify" not in captured
