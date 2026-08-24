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
from ktem.reasoning.mara_semantic_candidate_policy import candidate_bound_response
from ktem.reasoning.mara_semantic_proposition_packing import (
    SEMANTIC_PROPOSITION_VERIFIER_INPUT_TOKEN_BUDGET,
    SEMANTIC_PROPOSITION_VERIFIER_ITEM_CHARS,
)
from ktem.reasoning.mara_semantic_proposition_stages import _corrected_prompt
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
                _unknown_audit_response(
                    next(
                        (
                            candidate
                            for candidate in ("yes", "no", "unanswerable")
                            if f'"original_candidate":"{candidate}"'
                            in messages[1].content
                        ),
                        "yes",
                    )
                )
                if schema_name == "candidate_bound_unknown_audit"
                else _audit_response()
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


def _items() -> list[dict[str, Any]]:
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
            "evidence_relation": "proposition_support",
            "support_mode": "evidence_set",
            "proof_mode": "composite_conjunction",
            "jointly_complete": True,
            "each_premise_required": True,
            "premises": [
                {
                    "span_selector": "E1:S1",
                    "proposition_fragment": (
                        "Transfer was evaluated across two languages."
                    ),
                    "supports_slot_ids": [
                        "support:proposition",
                        "support:left_subject",
                    ],
                    "binds_proposition_slots": ["actor", "predicate"],
                },
                {
                    "span_selector": "E2:S1",
                    "proposition_fragment": (
                        "The experiment included monolingual baselines for comparison."
                    ),
                    "supports_slot_ids": [
                        "support:proposition",
                        "support:right_subject",
                    ],
                    "binds_proposition_slots": ["object"],
                },
            ],
        }
    )


def _insufficient_response() -> str:
    return json.dumps(
        {
            "verdict": "insufficient_evidence",
            "evidence_relation": "undetermined",
            "support_mode": "evidence_set",
            "proof_mode": "none",
            "jointly_complete": False,
            "each_premise_required": False,
            "premises": [],
            "unknown_assessment": {
                "reviewed_span_selectors": ["E1:S1", "E2:S1"],
                "unresolved_proposition_slots": [
                    "actor",
                    "predicate",
                    "object",
                ],
                "support_gap": "The reviewed evidence does not bind every slot.",
                "contradiction_gap": "No reviewed span explicitly contradicts it.",
            },
        }
    )


def _audit_response() -> str:
    premise_specs = [
        (["actor", "predicate"], {"actor": "Transfer", "predicate": "evaluated"}),
        (["object"], {"object": "monolingual baselines"}),
    ]
    return json.dumps(
        {
            "premise_checks": [
                {
                    "premise_ref": f"P{index}",
                    "fragment_entailed": True,
                    "scope_consistent": True,
                    "proposition_bindings_valid": True,
                    "evidence_relation_valid": True,
                    "declared_proposition_slots": slots,
                    "proposition_slot_checks": [
                        {
                            "slot": slot,
                            "binding_valid": True,
                            "evidence_text": evidence[slot],
                        }
                        for slot in slots
                    ],
                }
                for index, (slots, evidence) in enumerate(premise_specs, start=1)
            ],
            "jointly_entails": True,
            "each_premise_required": True,
            "contradiction_free": True,
            "conclusion_check": {
                "conclusion_entailed": True,
                "actor_consistent": True,
                "predicate_consistent": True,
                "object_consistent": True,
                "polarity_consistent": True,
                "quantifier_consistent": True,
                "scope_consistent": True,
            },
        }
    )


def _unknown_audit_response(candidate: str = "yes") -> str:
    return json.dumps(
        {
            "audit_scope": "original_candidate_and_verifier_unknown_only",
            "audited_candidate": candidate,
            "audited_verdict": "insufficient_evidence",
            "audited_judgment": ("unknown"),
            "typed_conclusion_present": True,
            "reviewed_evidence_present": True,
            "support_gap_valid": True,
            "contradiction_gap_valid": True,
            "relationship_consistent": True,
            "replacement_candidate_allowed": False,
            "replacement_candidate": "",
        }
    )


def test_runtime_verifier_binds_candidate_and_caches_candidate_signature() -> None:
    llm = _RecordingLLM(_model_response())
    verifier = build_semantic_proposition_verifier(
        SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    )
    assert verifier is not None
    request = _request()
    bundle = EvidenceBundle(route="doc_text", items=_items())

    first = verifier(request, QUESTION, "unanswerable", bundle)
    second = verifier(request, QUESTION, "yes", bundle)
    third = verifier(request, QUESTION, "yes", bundle)

    assert first is not None
    assert second is not None
    assert third is not None
    assert second == third
    assert first["candidate_verification_status"] == "contradicted"
    assert second["candidate_verification_status"] == "supported"
    assert first["verifier_input_candidate"] == "unanswerable"
    assert second["verifier_input_candidate"] == "yes"
    assert first["replacement_candidate_allowed"] is False
    assert first["candidate_verification_audit"]["classification"] == (
        "explicit_contradiction"
    )
    assert first["candidate_verification_audit"]["audited_candidate"] == (
        "unanswerable"
    )
    assert first["candidate_verification_audit"]["audited_verdict"] == "yes"
    assert len(llm.calls) == 4
    assert [value["evidence_id"] for value in second["premises"]] == [
        identity_of(item).key for item in _items()
    ]
    assert second["verifier"]["contract_id"] == "grounded_semantic_verifier.v3"
    assert second["verifier"]["model"] == "semantic-test-model"
    assert second["verifier"]["seed"] == 17
    assert second["verifier"]["release_mode"] is False
    assert second["verifier"]["auditor_relationship"] == "same_instance"
    assert (
        second["verifier"]["semantic_pack_digest"]
        == bundle.metadata["semantic_proposition_verifier"]["semantic_pack_digest"]
    )
    messages, kwargs = llm.calls[0]
    assert "STRUCTURED CANDIDATE TO VERIFY:\nunanswerable" in messages[1].content
    assert "must not independently choose" in messages[0].content
    assert "at least one premise must explicitly anchor their action" in (
        messages[0].content
    )
    assert len(messages[1].content) <= SEMANTIC_PROPOSITION_VERIFIER_MAX_PROMPT_CHARS
    audit_messages, audit_kwargs = llm.calls[1]
    assert "READ-ONLY CANDIDATE BINDING:" in audit_messages[1].content
    assert "original_candidate=unanswerable" in audit_messages[1].content
    assert "verifier_judgment=yes" in audit_messages[1].content
    audit_properties = audit_kwargs["response_format"]["json_schema"]["schema"][
        "properties"
    ]
    assert "replacement_candidate" not in audit_properties
    assert "verdict" not in audit_properties
    assert kwargs["temperature"] == 0
    assert kwargs["top_p"] == 1
    assert kwargs["response_format"]["json_schema"]["strict"] is True
    assert bundle.metadata["semantic_proposition_verifier"]["cache_hit"] is True
    assert (
        bundle.metadata["semantic_proposition_verifier"][
            "replacement_candidate_allowed"
        ]
        is False
    )
    assert (
        bundle.metadata["semantic_proposition_verifier"]["actual_model_call_count"] == 4
    )


def test_insufficient_verdict_is_a_candidate_bound_audit_not_a_skipped_audit() -> None:
    llm = _RecordingLLM(_insufficient_response())
    verifier = build_semantic_proposition_verifier(
        SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    )
    assert verifier is not None
    bundle = EvidenceBundle(route="doc_text", items=_items())

    result = verifier(_request(), QUESTION, "yes", bundle)

    assert result is not None
    assert result["verdict"] == "insufficient_evidence"
    assert result["candidate_verification_status"] == "unknown"
    audit = result["candidate_verification_audit"]
    assert audit["mode"] == "candidate_bound_unknown_audit"
    assert audit["audited_candidate"] == "yes"
    assert audit["audited_verdict"] == "insufficient_evidence"
    assert audit["classification"] == "unknown"
    assert audit["replacement_candidate_allowed"] is False
    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["audit_status"] == "candidate_bound"
    assert trace["replacement_candidate_allowed"] is False
    assert trace["candidate_verification_audit"]["status"] == "passed"
    assert trace["candidate_verification_audit"]["classification"] == ("unknown")
    assert trace["unknown"] is True
    assert trace["explicit_contradiction"] is False
    assert trace["candidate_verifier_disagreement"] is False
    assert trace["audit_model_call_count"] == 1
    assert trace["auditor_attempt_id"]
    assert len(llm.calls) == 2


def test_unknown_candidate_audit_cannot_supply_or_replace_a_candidate() -> None:
    result = candidate_bound_response({"verdict": "insufficient_evidence"}, "no")

    assert result["verdict"] == "insufficient_evidence"
    assert result["verifier_input_candidate"] == "no"
    assert result["candidate_verification_status"] == "unknown"
    assert result["candidate_verification_audit"]["classification"] == "unknown"
    assert result["candidate_verification_audit"]["audited_candidate"] == "no"
    assert result["candidate_verification_audit"]["audited_verdict"] == (
        "insufficient_evidence"
    )
    assert result["candidate_verification_audit"]["status"] == "failed"
    assert result["replacement_candidate_allowed"] is False


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

    assert len(llm.calls) == 2
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
        SimpleNamespace(
            answering_pipeline=SimpleNamespace(llm=llm),
            semantic_proposition_debug_trace=True,
        )
    )
    assert verifier is not None
    bundle = EvidenceBundle(route="doc_text", items=_items())

    assert verifier(_request(), QUESTION, "unanswerable", bundle) is None
    assert verifier(_request(), QUESTION, "unanswerable", bundle) is None

    assert llm.call_count == 1
    trace = bundle.metadata["semantic_proposition_verifier"]
    assert trace["status"] == "cached_failure"
    assert trace["reason"] == reason
    transaction = trace["debug_trace"]["events"][0]["transaction"]
    attempt = transaction["proposal"]["attempts"][0]
    assert attempt["provider_failure_reason"] == reason
    assert attempt["provider_failure_detail"] == message


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


def test_proposal_correction_prompt_is_specific_to_conflicting_unknown_assessment() -> None:
    corrected = _corrected_prompt(
        "Return one semantic proposition object.",
        "unexpected_unknown_assessment",
    )

    assert "unexpected_unknown_assessment" in corrected
    assert "omit unknown_assessment" in corrected
    assert "supported or contradicted" in corrected
    assert "unknown requires" in corrected


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
    response["premises"][1]["span_selector"] = "E1:S2"
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
    items = _items()
    response = json.loads(_model_response())
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
        "yes",
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
