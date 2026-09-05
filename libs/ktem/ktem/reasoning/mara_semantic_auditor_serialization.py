"""Exact Stage 9 auditor request serialization and pre-transport trace."""

from __future__ import annotations

import json
import logging
from collections.abc import Collection
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable

from ktem.docqa.canonical_serialization import (
    CANONICAL_SERIALIZER_IDENTITY,
    canonical_digest,
    canonical_json,
)

from kotaemon.base import HumanMessage, SystemMessage

from .mara_qasper_candidate_budget import candidate_input_token_measurement
from .mara_semantic_audit_preflight import PRE_AUDIT_SCHEMA_VALIDATION_FAILED
from .mara_semantic_auditor_prompt import (
    SEMANTIC_ENTAILMENT_AUDIT_MAX_PROMPT_CHARS,
    semantic_entailment_audit_prompt_unbounded,
)
from .mara_semantic_entailment_audit import (
    SEMANTIC_ENTAILMENT_AUDIT_MAX_TOKENS,
    SEMANTIC_ENTAILMENT_AUDIT_SYSTEM_PROMPT,
    semantic_entailment_audit_response_format,
)
from .mara_semantic_proposition_debug import provider_failure
from .mara_semantic_proposition_stage_runtime import StageCallResult

AUDITOR_CANONICAL_SERIALIZER_IDENTITY = (
    "kotaemon_chat_openai_prepare_message+canonical_json_utf8_v1"
)
SEMANTIC_ENTAILMENT_AUDIT_MAX_MODEL_LEN = 4096
SEMANTIC_ENTAILMENT_AUDIT_TOKEN_HEADROOM = 128
SEMANTIC_ENTAILMENT_AUDIT_INPUT_TOKEN_LIMIT = (
    SEMANTIC_ENTAILMENT_AUDIT_MAX_MODEL_LEN
    - SEMANTIC_ENTAILMENT_AUDIT_MAX_TOKENS
    - SEMANTIC_ENTAILMENT_AUDIT_TOKEN_HEADROOM
)

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class CanonicalSemanticAuditorRequest:
    prompt: str
    messages: tuple[Any, ...]
    serialized_messages: list[dict[str, Any]]
    parameters: dict[str, Any]
    request_snapshot: dict[str, Any]
    trace: dict[str, Any]
    failure_reason: str = ""


def call_canonical_semantic_auditor(
    llm: Any,
    prompt: str,
    *,
    premise_labels: list[str],
    seed: int,
    premise_slot_expectations: dict[str, Collection[str]] | None,
    premise_slot_evidence: dict[str, dict[str, Any]] | None,
    response_format_factory: Callable[..., dict[str, Any]] = (
        semantic_entailment_audit_response_format
    ),
) -> StageCallResult:
    try:
        response_format = response_format_factory(
            premise_labels,
            premise_slot_expectations=premise_slot_expectations,
            premise_slot_evidence=premise_slot_evidence,
        )
    except ValueError as exc:
        return StageCallResult(
            None,
            PRE_AUDIT_SCHEMA_VALIDATION_FAILED,
            str(exc)[:4000],
            False,
        )
    request = canonical_semantic_auditor_request(
        llm,
        prompt,
        response_format=response_format,
        seed=seed,
    )
    if request.failure_reason:
        return StageCallResult(
            None,
            request.failure_reason,
            json.dumps(request.trace, ensure_ascii=False, separators=(",", ":"))[:4000],
            False,
            request_snapshot=request.request_snapshot,
        )
    try:
        return StageCallResult(
            llm(list(request.messages), **request.parameters),
            request_snapshot=request.request_snapshot,
        )
    except Exception as exc:
        LOGGER.exception("Semantic entailment audit model call failed")
        failure, detail = provider_failure(exc)
        return StageCallResult(
            None,
            failure,
            detail,
            request_snapshot=request.request_snapshot,
        )


def canonical_semantic_entailment_audit_request(
    llm: Any | None,
    proposition: Any,
    conclusion: Any,
    proof_mode: str,
    premises: list[dict[str, Any]],
    *,
    original_candidate: str = "",
    candidate_judgment: str = "",
    premise_slot_evidence: dict[str, dict[str, Any]] | None = None,
    semantic_pack_identity: dict[str, str] | None = None,
    seed: int,
) -> CanonicalSemanticAuditorRequest:
    prompt = semantic_entailment_audit_prompt_unbounded(
        proposition,
        conclusion,
        proof_mode,
        premises,
        original_candidate=original_candidate,
        candidate_judgment=candidate_judgment,
        premise_slot_evidence=premise_slot_evidence,
        semantic_pack_identity=semantic_pack_identity,
    )
    labels = [f"P{index}" for index in range(1, len(premises) + 1)]
    expectations = {
        label: tuple(str(slot) for slot in premise.get("binds_proposition_slots") or [])
        for label, premise in zip(labels, premises)
    }
    response_format = semantic_entailment_audit_response_format(
        labels,
        premise_slot_expectations=expectations,
        premise_slot_evidence=premise_slot_evidence,
    )
    return canonical_semantic_auditor_request(
        llm,
        prompt,
        response_format=response_format,
        seed=seed,
    )


def canonical_semantic_auditor_request(
    llm: Any | None,
    prompt: str,
    *,
    response_format: dict[str, Any],
    seed: int,
) -> CanonicalSemanticAuditorRequest:
    messages = (
        SystemMessage(content=SEMANTIC_ENTAILMENT_AUDIT_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    )
    serialized_messages = [message.to_openai_format() for message in messages]
    parameters = {
        "max_tokens": SEMANTIC_ENTAILMENT_AUDIT_MAX_TOKENS,
        "response_format": deepcopy(response_format),
        "temperature": 0,
        "top_p": 1,
        "seed": seed,
    }
    token_measurement = _stable_token_measurement(
        llm,
        list(messages),
        response_format,
    )
    trace, failure_reason = _serialization_trace(
        prompt,
        serialized_messages,
        parameters,
        token_measurement,
    )
    request_snapshot = {
        "messages": deepcopy(serialized_messages),
        "parameters": deepcopy(parameters),
        "serialization": deepcopy(trace),
    }
    return CanonicalSemanticAuditorRequest(
        prompt=prompt,
        messages=messages,
        serialized_messages=serialized_messages,
        parameters=parameters,
        request_snapshot=request_snapshot,
        trace=trace,
        failure_reason=failure_reason,
    )


def _stable_token_measurement(
    llm: Any | None,
    messages: list[Any],
    response_format: dict[str, Any],
) -> dict[str, Any]:
    measurement = candidate_input_token_measurement(llm, messages, response_format)
    if (
        int(measurement.get("estimated_input_tokens") or -1) >= 0
        and measurement.get("tokenizer_identity") != "fallback:conservative_utf8"
    ):
        return measurement
    fallback = _canonical_utf8_token_estimate(messages, response_format)
    fallback["source_tokenizer_failed"] = bool(measurement.get("tokenizer_failed"))
    fallback["source_tokenizer_identity"] = str(
        measurement.get("tokenizer_identity") or ""
    )
    fallback["source_tokenizer_failure_reason"] = str(
        measurement.get("tokenizer_failure_reason") or ""
    )
    return fallback


def _canonical_utf8_token_estimate(
    messages: list[Any],
    response_format: dict[str, Any],
) -> dict[str, Any]:
    serialized = [message.to_openai_format() for message in messages]
    message_bytes = len(canonical_json(serialized).encode("utf-8"))
    schema_bytes = len(canonical_json(response_format).encode("utf-8"))
    message_tokens = max(1, (message_bytes + 3) // 4)
    schema_tokens = max(1, (schema_bytes + 3) // 4)
    return {
        "estimated_input_tokens": message_tokens + schema_tokens,
        "message_tokens": message_tokens,
        "schema_tokens": schema_tokens,
        "tokenizer_identity": "fallback:canonical_utf8_quarter_estimate_v1",
        "tokenizer_method": "canonical_utf8_bytes_ceiling_div4",  # gitleaks:allow
        "tokenizer_exact": False,
        "tokenizer_endpoint": "",
        "tokenizer_failed": False,
        "tokenizer_failure_reason": "",
    }


def _serialization_trace(
    prompt: str,
    serialized_messages: list[dict[str, Any]],
    parameters: dict[str, Any],
    token_measurement: dict[str, Any],
) -> tuple[dict[str, Any], str]:
    prompt_chars = len(prompt)
    message_chars = sum(
        len(str(message.get("content") or "")) for message in serialized_messages
    )
    message_tokens = int(token_measurement.get("message_tokens") or 0)
    schema_tokens = int(token_measurement.get("schema_tokens") or 0)
    measured_request_tokens = int(token_measurement.get("estimated_input_tokens") or 0)
    char_exceeded = prompt_chars > SEMANTIC_ENTAILMENT_AUDIT_MAX_PROMPT_CHARS
    token_limit_enforced = bool(token_measurement.get("tokenizer_exact"))
    token_exceeded = bool(
        token_limit_enforced
        and message_tokens > SEMANTIC_ENTAILMENT_AUDIT_INPUT_TOKEN_LIMIT
    )
    failure_reason = (
        "audit_prompt_bound_exceeded"
        if char_exceeded
        else "audit_prompt_token_bound_exceeded"
        if token_exceeded
        else ""
    )
    failed_before_transport = bool(failure_reason)
    trace = {
        "contract_id": "semantic_auditor_request_serialization.v1",
        "serializer_identity": AUDITOR_CANONICAL_SERIALIZER_IDENTITY,
        "canonical_serializer_identity": CANONICAL_SERIALIZER_IDENTITY,
        "message_digest": canonical_digest(serialized_messages),
        "request_digest": canonical_digest(
            {"messages": serialized_messages, "parameters": parameters}
        ),
        "response_schema_digest": canonical_digest(parameters["response_format"]),
        "prompt_char_count": prompt_chars,
        "message_char_count": message_chars,
        "prompt_char_limit": SEMANTIC_ENTAILMENT_AUDIT_MAX_PROMPT_CHARS,
        "input_token_count": message_tokens,
        "message_token_count": message_tokens,
        "schema_token_count": schema_tokens,
        "message_and_schema_token_count": measured_request_tokens,
        "input_token_limit": SEMANTIC_ENTAILMENT_AUDIT_INPUT_TOKEN_LIMIT,
        "max_model_len": SEMANTIC_ENTAILMENT_AUDIT_MAX_MODEL_LEN,
        "max_output_tokens": SEMANTIC_ENTAILMENT_AUDIT_MAX_TOKENS,
        "token_headroom": SEMANTIC_ENTAILMENT_AUDIT_TOKEN_HEADROOM,
        "tokenizer_identity": str(token_measurement.get("tokenizer_identity") or ""),
        "tokenizer_method": str(token_measurement.get("tokenizer_method") or ""),
        "tokenizer_exact": bool(token_measurement.get("tokenizer_exact")),
        "tokenizer_endpoint": str(token_measurement.get("tokenizer_endpoint") or ""),
        "tokenizer_failed": bool(token_measurement.get("tokenizer_failed")),
        "tokenizer_failure_reason": str(
            token_measurement.get("tokenizer_failure_reason") or ""
        ),
        "token_limit_enforced": token_limit_enforced,
        "character_limit_exceeded": char_exceeded,
        "token_limit_exceeded": token_exceeded,
        "failed_before_transport": failed_before_transport,
        "transport_status": (
            "failed_before_transport"
            if failed_before_transport
            else "ready_for_transport"
        ),
        "failure_reason": failure_reason,
    }
    for key in (
        "source_tokenizer_failed",
        "source_tokenizer_identity",
        "source_tokenizer_failure_reason",
    ):
        if key in token_measurement:
            trace[key] = token_measurement[key]
    return trace, failure_reason
