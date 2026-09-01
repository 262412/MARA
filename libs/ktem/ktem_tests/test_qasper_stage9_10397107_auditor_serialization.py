from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from ktem.docqa.question_proposition import (
    build_question_proposition,
    proposition_evidence_bindings,
    typed_conclusion,
)
from ktem.reasoning.mara_semantic_entailment_audit import (
    SEMANTIC_ENTAILMENT_AUDIT_MAX_PROMPT_CHARS,
    semantic_entailment_audit_prompt,
)

FIXTURE = (
    Path(__file__).parent / "fixtures" / "qasper_stage9_10397107_auditor_payload.json"
)


def _fixture() -> dict[str, Any]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def _inputs() -> tuple[dict[str, Any], Any, Any]:
    payload = _fixture()
    proposition = build_question_proposition(payload["question"])
    conclusion = typed_conclusion(proposition, "yes")
    return payload, proposition, conclusion


def _legacy_prompt(payload: dict[str, Any], proposition: Any, conclusion: Any) -> str:
    old_payload = {
        "original_candidate": payload["original_candidate"],
        "candidate_judgment": payload["candidate_judgment"],
        "question_proposition": proposition.as_dict(),
        "typed_conclusion": conclusion.as_dict(),
        "semantic_pack_identity": payload["semantic_pack_identity"],
        "proof_mode": payload["proof_mode"],
        "target_proposition_slot_bindings": proposition_evidence_bindings(proposition),
        "premises": [
            {
                "premise_ref": f"P{index}",
                "quote": premise["quote"],
                "proposition_fragment": premise["proposition_fragment"],
                "binds_proposition_slots": premise["binds_proposition_slots"],
                "local_proposition_slot_contributions": payload[
                    "premise_slot_evidence"
                ][f"P{index}"],
                "semantic_alignment": premise["semantic_alignment"],
                "evidence_relation": str(premise.get("evidence_relation") or ""),
            }
            for index, premise in enumerate(payload["premises"], start=1)
        ],
    }
    return "/no_think\nAUDIT THIS PROOF PROPOSAL:\n" + json.dumps(
        old_payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _prompt(payload: dict[str, Any], proposition: Any, conclusion: Any) -> str:
    return semantic_entailment_audit_prompt(
        proposition,
        conclusion,
        payload["proof_mode"],
        payload["premises"],
        original_candidate=payload["original_candidate"],
        candidate_judgment=payload["candidate_judgment"],
        premise_slot_evidence=payload["premise_slot_evidence"],
        semantic_pack_identity=payload["semantic_pack_identity"],
    )


def _all_string_values(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [item for child in value.values() for item in _all_string_values(child)]
    if isinstance(value, list):
        return [item for child in value for item in _all_string_values(child)]
    return [value] if isinstance(value, str) else []


def test_job_10397107_payload_serializes_each_frozen_quote_once() -> None:
    payload, proposition, conclusion = _inputs()

    legacy = _legacy_prompt(payload, proposition, conclusion)
    prompt = _prompt(payload, proposition, conclusion)
    serialized = json.loads(prompt.split("AUDIT THIS PROOF PROPOSAL:\n", 1)[1])
    string_values = _all_string_values(serialized)

    assert len(legacy) == payload["source"]["observed_legacy_prompt_chars"] == 8044
    assert len(legacy) > payload["source"]["prompt_char_limit"]
    assert len(prompt) <= SEMANTIC_ENTAILMENT_AUDIT_MAX_PROMPT_CHARS
    assert len(serialized["frozen_evidence_spans"]) == 3
    for index, premise in enumerate(payload["premises"], start=1):
        label = f"P{index}"
        assert string_values.count(premise["quote"]) == 1
        serialized_premise = serialized["premises"][index - 1]
        assert serialized_premise["frozen_span_ref"] == f"{label}:quote"
        assert serialized_premise["proposition_fragment_ref"] == f"{label}:quote"
        assert serialized_premise["proposition_fragment_digest"]
        for evidence in serialized_premise[
            "local_proposition_slot_contributions"
        ].values():
            assert evidence["source_span_ref"] == f"{label}:quote"
            assert evidence["text_digest"]
            assert "text" not in evidence
        alignment = serialized_premise["semantic_alignment"]
        assert alignment["source_span_ref"] == f"{label}:quote"
        assert alignment["alignment_digest"]
        assert "covered_object_tokens" not in alignment
        assert "semantic_matches" not in alignment
        assert "semantic_rule_ids" not in alignment


def test_job_10397107_request_matches_real_chatopenai_message_adapter() -> None:
    from ktem.reasoning.mara_semantic_auditor_serialization import (
        AUDITOR_CANONICAL_SERIALIZER_IDENTITY,
        canonical_semantic_entailment_audit_request,
    )

    from kotaemon.llms import ChatOpenAI

    payload, proposition, conclusion = _inputs()
    request = canonical_semantic_entailment_audit_request(
        None,
        proposition,
        conclusion,
        payload["proof_mode"],
        payload["premises"],
        original_candidate=payload["original_candidate"],
        candidate_judgment=payload["candidate_judgment"],
        premise_slot_evidence=payload["premise_slot_evidence"],
        semantic_pack_identity=payload["semantic_pack_identity"],
        seed=20260725,
    )
    adapter = ChatOpenAI(
        api_key="local",
        base_url="http://127.0.0.1:1/v1",
        model="adapter-characterization",
        max_retries=0,
    )

    assert (
        adapter.prepare_message(list(request.messages)) == request.serialized_messages
    )
    assert request.failure_reason == ""
    assert request.trace["serializer_identity"] == (
        AUDITOR_CANONICAL_SERIALIZER_IDENTITY
    )
    assert request.trace["message_digest"]
    assert request.trace["prompt_char_count"] == len(request.prompt)
    assert request.trace["input_token_count"] > 0
    assert request.trace["input_token_count"] == request.trace["message_token_count"]
    assert request.trace["message_and_schema_token_count"] == (
        request.trace["message_token_count"] + request.trace["schema_token_count"]
    )
    assert request.trace["failed_before_transport"] is False


def test_auditor_message_budget_does_not_charge_response_schema_tokens() -> None:
    from ktem.reasoning.mara_semantic_auditor_serialization import (
        canonical_semantic_auditor_request,
    )

    class _CharacterTokenizer:
        model_name = "stage9-character-tokenizer"

        def encode(self, text: str, **_: Any) -> list[int]:
            return [0] * len(text)

    request = canonical_semantic_auditor_request(
        _CharacterTokenizer(),
        "small prompt",
        response_format={"schema": "x" * 5000},
        seed=20260725,
    )

    assert request.trace["tokenizer_exact"] is True
    assert request.trace["message_token_count"] < request.trace["input_token_limit"]
    assert (
        request.trace["message_and_schema_token_count"]
        > request.trace["input_token_limit"]
    )
    assert request.failure_reason == ""


def test_auditor_bound_failure_records_serialization_before_transport() -> None:
    from ktem.reasoning.mara_semantic_auditor_serialization import (
        canonical_semantic_entailment_audit_request,
    )

    payload, proposition, conclusion = _inputs()
    premises = deepcopy(payload["premises"])
    premises[0]["quote"] += "x" * 9000
    premises[0]["proposition_fragment"] = premises[0]["quote"]
    request = canonical_semantic_entailment_audit_request(
        None,
        proposition,
        conclusion,
        payload["proof_mode"],
        premises,
        original_candidate=payload["original_candidate"],
        candidate_judgment=payload["candidate_judgment"],
        premise_slot_evidence=payload["premise_slot_evidence"],
        semantic_pack_identity=payload["semantic_pack_identity"],
        seed=20260725,
    )

    trace = request.trace
    assert request.failure_reason == "audit_prompt_bound_exceeded"
    assert trace["message_digest"]
    assert trace["prompt_char_count"] > trace["prompt_char_limit"]
    assert trace["input_token_count"] > 0
    assert trace["input_token_limit"] > 0
    assert trace["failed_before_transport"] is True
    assert trace["transport_status"] == "failed_before_transport"
    assert request.request_snapshot["serialization"] == trace


def test_stage9_bound_failure_is_a_zero_call_traced_attempt() -> None:
    from ktem.reasoning.mara_semantic_proposition_data_lineage import (
        record_audit_data_lineage,
    )
    from ktem.reasoning.mara_semantic_proposition_stages import audit_stage

    class _NeverCalled:
        model_name = "stage9-characterization"

        def __call__(self, messages: Any, **kwargs: Any) -> Any:
            del messages, kwargs
            raise AssertionError("auditor transport must not start")

    evidence = {
        "P1": {
            "actor": {
                "text": "authors",
                "span_start": 0,
                "span_end": 7,
                "clause_ref": "C1",
                "clause_start": 0,
                "clause_end": 7,
                "evidence_ref": "P1:actor",
            }
        }
    }
    stage = audit_stage(
        _NeverCalled(),
        "x" * (SEMANTIC_ENTAILMENT_AUDIT_MAX_PROMPT_CHARS + 1),
        1,
        seed=20260725,
        premise_slot_expectations={"P1": ("actor",)},
        premise_slot_evidence=evidence,
    )

    assert stage.call_count == 0
    assert stage.failure_reason == "audit_prompt_bound_exceeded"
    assert len(stage.attempts) == 1
    snapshot = stage.attempts[0].request_snapshot
    assert snapshot is not None
    serialization = snapshot["serialization"]
    assert serialization["message_digest"]
    assert serialization["failed_before_transport"] is True

    diagnostics: dict[str, Any] = {}
    record_audit_data_lineage(diagnostics, stage)
    lineage = diagnostics["semantic_data_lineage"]
    [attempt] = lineage["audit"]["attempts"]
    assert attempt["serializer_identity"] == serialization["serializer_identity"]
    assert attempt["message_digest"] == serialization["message_digest"]
    assert attempt["prompt_char_count"] == serialization["prompt_char_count"]
    assert attempt["input_token_count"] == serialization["input_token_count"]
    assert attempt["failed_before_transport"] is True
    assert lineage["first_inconsistency"]["stage"] == ("auditor_message_serialization")
