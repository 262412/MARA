from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.query_planning import build_query_plan
from ktem.reasoning.mara_semantic_proposition_verifier import (
    SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS,
    build_semantic_proposition_verifier,
)

QUESTION = "Did the authors compare cross-lingual and single-language evaluation?"


class _SequenceLLM:
    model_name = "semantic-test-model"

    def __init__(self, responses: list[Any]) -> None:
        self.responses = list(responses)
        self.calls: list[tuple[Any, dict[str, Any]]] = []

    def __call__(self, messages: Any, **kwargs: Any) -> Any:
        self.calls.append((messages, kwargs))
        return self.responses.pop(0)


def _response(
    text: str,
    *,
    completion_tokens: int = 100,
    finish_reason: str = "stop",
) -> Any:
    return SimpleNamespace(
        text=text,
        completion_tokens=completion_tokens,
        additional_kwargs={"finish_reason": finish_reason},
    )


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


def _proposal() -> str:
    slot_ids = [
        slot.slot_id
        for slot in _request().query_plan.evidence_slots
        if slot.required_for_verification
    ]
    return json.dumps(
        {
            "verdict": "yes",
            "support_mode": "evidence_set",
            "jointly_complete": True,
            "each_premise_required": True,
            "premises": [
                {
                    "evidence_ref": "E1",
                    "quote": _items()[0]["text"],
                    "proposition_fragment": "cross-lingual evaluation was performed",
                    "supports_slot_ids": slot_ids[:2],
                },
                {
                    "evidence_ref": "E2",
                    "quote": _items()[1]["text"],
                    "proposition_fragment": (
                        "single-language baselines were included for comparison"
                    ),
                    "supports_slot_ids": [slot_ids[0], slot_ids[-1]],
                },
            ],
        }
    )


def _audit(*, second_fragment_entailed: bool = True) -> str:
    return json.dumps(
        {
            "premise_checks": [
                {
                    "premise_ref": "P1",
                    "fragment_entailed": True,
                    "scope_consistent": True,
                },
                {
                    "premise_ref": "P2",
                    "fragment_entailed": second_fragment_entailed,
                    "scope_consistent": True,
                },
            ],
            "jointly_entails": second_fragment_entailed,
            "each_premise_required": second_fragment_entailed,
            "contradiction_free": True,
        }
    )


def _verifier(llm: _SequenceLLM, *, debug: bool = False) -> Any:
    return build_semantic_proposition_verifier(
        SimpleNamespace(
            answering_pipeline=SimpleNamespace(llm=llm),
            semantic_proposition_debug_trace=debug,
        )
    )


def test_runtime_requires_an_independent_entailment_audit_before_commit() -> None:
    llm = _SequenceLLM([_response(_proposal()), _response(_audit())])
    verifier = _verifier(llm)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    result = verifier(_request(), QUESTION, "unanswerable", bundle)

    assert result is not None
    assert result["contract_id"] == "semantic_proposition_verdict.v2"
    assert result["verdict"] == "yes"
    audit = result["entailment_audit"]
    assert audit["contract_id"] == "semantic_entailment_audit.v1"
    assert audit["status"] == "verified"
    assert audit["premise_count"] == 2
    assert len(llm.calls) == 2
    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["audit_status"] == "verified"
    assert trace["audit_model_call_count"] == 1


def test_runtime_can_route_the_audit_to_a_dedicated_model() -> None:
    proposal_llm = _SequenceLLM([_response(_proposal())])
    audit_llm = _SequenceLLM([_response(_audit())])
    audit_llm.model_name = "dedicated-audit-model"
    verifier = build_semantic_proposition_verifier(
        SimpleNamespace(answering_pipeline=SimpleNamespace(llm=proposal_llm)),
        audit_llm=audit_llm,
    )
    assert verifier is not None
    bundle = EvidenceBundle(route="doc_text", items=_items())

    result = verifier(_request(), QUESTION, "unanswerable", bundle)

    assert result is not None
    assert len(proposal_llm.calls) == 1
    assert len(audit_llm.calls) == 1
    assert result["entailment_audit"]["auditor"]["model"] == ("dedicated-audit-model")
    assert bundle.metadata["semantic_proposition_verifier"]["audit_model"] == (
        "dedicated-audit-model"
    )


def test_runtime_downgrades_a_self_attested_but_unaudited_extension() -> None:
    llm = _SequenceLLM(
        [_response(_proposal()), _response(_audit(second_fragment_entailed=False))]
    )
    verifier = _verifier(llm)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    result = verifier(_request(), QUESTION, "yes", bundle)

    assert result is not None
    assert result["verdict"] == "insufficient_evidence"
    assert result["premises"] == []
    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["status"] == "audit_rejected"
    assert trace["audit_status"] == "rejected"
    assert trace["audit_reason"] == "premise_fragment_not_entailed"


def test_runtime_retries_one_malformed_proposal_then_audits_it() -> None:
    llm = _SequenceLLM(
        [
            _response("{", completion_tokens=SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS),
            _response(_proposal()),
            _response(_audit()),
        ]
    )
    verifier = _verifier(llm)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    result = verifier(_request(), QUESTION, "yes", bundle)

    assert result is not None and result["verdict"] == "yes"
    assert len(llm.calls) == 3
    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["proposal_retry_count"] == 1
    assert trace["initial_parse_failure_reason"] == "json_decode_error"


def test_runtime_classifies_exhausted_output_without_recording_response_text() -> None:
    llm = _SequenceLLM(
        [
            _response(
                "{",
                completion_tokens=SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS,
                finish_reason="length",
            ),
            _response(
                "{",
                completion_tokens=SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS,
                finish_reason="length",
            ),
        ]
    )
    verifier = _verifier(llm)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    assert verifier(_request(), QUESTION, "yes", bundle) is None

    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["reason"] == "provider_output_truncated"
    assert trace["parse_failure_reason"] == "json_decode_error"
    assert trace["response_finish_reason"] == "length"
    assert trace["response_completion_tokens"] == (
        SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS
    )
    assert trace["response_chars"] == 1
    assert "response_text" not in trace
    assert "debug_trace" not in trace


def test_debug_trace_records_every_proposal_and_audit_output_without_changing_result() -> (
    None
):
    llm = _SequenceLLM([_response(_proposal()), _response(_audit())])
    verifier = _verifier(llm, debug=True)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    result = verifier(_request(), QUESTION, "unanswerable", bundle)

    assert result is not None and result["verdict"] == "yes"
    debug = bundle.metadata["semantic_proposition_verifier"]["debug_trace"]
    assert debug["contract_id"] == "semantic_proposition_debug_trace.v1"
    [event] = debug["events"]
    assert event["event"] == "model_transaction"
    assert event["auditor_relationship"] == "same_instance"
    assert event["transaction"]["proposal"]["attempts"][0]["raw_response"] == (
        _proposal()
    )
    assert (
        event["transaction"]["proposal"]["attempts"][0]["parsed_value"]["verdict"]
        == "yes"
    )
    assert event["transaction"]["audit"]["attempts"][0]["raw_response"] == (_audit())
    assert (
        event["transaction"]["audit"]["attempts"][0]["parsed_value"]["jointly_entails"]
        is True
    )


def test_debug_trace_preserves_cache_reuse_after_a_rejected_audit() -> None:
    llm = _SequenceLLM(
        [_response(_proposal()), _response(_audit(second_fragment_entailed=False))]
    )
    verifier = _verifier(llm, debug=True)
    bundle = EvidenceBundle(route="doc_text", items=_items())

    first = verifier(_request(), QUESTION, "yes", bundle)
    second = verifier(_request(), QUESTION, "yes", bundle)

    assert first == second
    debug = bundle.metadata["semantic_proposition_verifier"]["debug_trace"]
    assert [event["event"] for event in debug["events"]] == [
        "model_transaction",
        "cache_reuse",
    ]
    assert debug["events"][0]["outcome"]["audit_status"] == "rejected"
    assert debug["events"][1]["source_event_index"] == 1
    assert debug["events"][1]["cached_outcome"]["audit_status"] == "rejected"


def test_debug_trace_can_be_enabled_by_the_slurm_environment(monkeypatch: Any) -> None:
    monkeypatch.setenv("MARA_SEMANTIC_PROPOSITION_DEBUG_TRACE", "1")
    llm = _SequenceLLM([_response(_proposal()), _response(_audit())])
    verifier = build_semantic_proposition_verifier(
        SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    )
    assert verifier is not None
    bundle = EvidenceBundle(route="doc_text", items=_items())

    verifier(_request(), QUESTION, "unanswerable", bundle)

    assert (
        bundle.metadata["semantic_proposition_verifier"]["debug_trace"]["contract_id"]
        == "semantic_proposition_debug_trace.v1"
    )
