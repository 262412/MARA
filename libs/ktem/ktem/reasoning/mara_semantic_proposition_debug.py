from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

SEMANTIC_PROPOSITION_DEBUG_CONTRACT = "semantic_proposition_debug_trace.v2"
SEMANTIC_PROPOSITION_DEBUG_ENV = "MARA_SEMANTIC_PROPOSITION_DEBUG_TRACE"
SEMANTIC_PROPOSITION_DEBUG_MAX_EVENTS = 16
SEMANTIC_PROPOSITION_DEBUG_RESPONSE_CHARS = 16_000


@dataclass(frozen=True)
class SemanticPropositionStageAttempt:
    response: Any | None
    parsed_value: dict[str, Any] | None
    correction_reason: str
    parse_failure_reason: str
    provider_failure_reason: str
    provider_failure_detail: str


def semantic_proposition_debug_enabled(pipeline: Any) -> bool:
    configured = getattr(pipeline, "semantic_proposition_debug_trace", None)
    if configured is not None:
        return _truthy(configured)
    return _truthy(os.getenv(SEMANTIC_PROPOSITION_DEBUG_ENV, ""))


def semantic_auditor_relationship(
    proposal_llm: Any,
    audit_llm: Any,
    *,
    proposal_model: str,
    audit_model: str,
) -> str:
    if proposal_llm is audit_llm:
        return "same_instance"
    if proposal_model == audit_model:
        return "distinct_instance_same_model"
    return "distinct_model"


def semantic_transaction_debug(
    enabled: bool,
    proposal: Any,
    audit: Any | None,
    *,
    proposal_model: str,
    audit_model: str,
    auditor_relationship: str,
) -> dict[str, Any] | None:
    if not enabled:
        return None
    return {
        "contract_id": SEMANTIC_PROPOSITION_DEBUG_CONTRACT,
        "proposal_model": proposal_model,
        "audit_model": audit_model,
        "auditor_relationship": auditor_relationship,
        "proposal": _stage_debug(proposal),
        "audit": _stage_debug(audit) if audit is not None else {"status": "not_run"},
    }


class SemanticPropositionDebugRecorder:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled
        self.events: list[dict[str, Any]] = []
        self.event_count = 0
        self.dropped_event_count = 0
        self.cache_event_indices: dict[str, int] = {}

    def record_model_transaction(
        self,
        cache_key: str,
        question: str,
        packing: Any,
        slots: list[dict[str, str]],
        *,
        status: str,
        reason: str,
        verdict: str,
        diagnostics: dict[str, Any],
        transaction: dict[str, Any] | None,
    ) -> None:
        if not self.enabled:
            return
        event = self._base_event(
            "model_transaction", cache_key, question, packing, slots
        )
        event.update(
            {
                "auditor_relationship": str(
                    (transaction or {}).get("auditor_relationship")
                    or diagnostics.get("auditor_relationship")
                    or ""
                ),
                "outcome": {
                    "status": status,
                    "reason": reason,
                    "verdict": verdict,
                    "audit_status": str(diagnostics.get("audit_status") or ""),
                    "audit_reason": str(diagnostics.get("audit_reason") or ""),
                    "proof_mode": str(diagnostics.get("proof_mode") or ""),
                    "typed_conclusion": deepcopy(
                        diagnostics.get("typed_conclusion") or {}
                    ),
                    "conclusion_audit": deepcopy(
                        diagnostics.get("conclusion_audit") or {}
                    ),
                    "recovery_transitions": deepcopy(
                        diagnostics.get("recovery_transitions") or []
                    ),
                },
                "transaction": deepcopy(transaction or {}),
            }
        )
        self.cache_event_indices[cache_key] = self._append(event)

    def record_cache_reuse(
        self,
        cache_key: str,
        question: str,
        packing: Any,
        slots: list[dict[str, str]],
        *,
        cached: dict[str, Any] | None,
        diagnostics: dict[str, Any],
        failure_reason: str,
    ) -> None:
        if not self.enabled:
            return
        event = self._base_event("cache_reuse", cache_key, question, packing, slots)
        event.update(
            {
                "source_event_index": self.cache_event_indices.get(cache_key),
                "cache_source": "route_local_semantic_pack",
                "cached_outcome": {
                    "status": "cache_hit" if cached is not None else "cached_failure",
                    "reason": (
                        "evidence_signature_reused"
                        if cached is not None
                        else failure_reason
                    ),
                    "verdict": str((cached or {}).get("verdict") or ""),
                    "audit_status": str(diagnostics.get("audit_status") or ""),
                    "audit_reason": str(diagnostics.get("audit_reason") or ""),
                },
            }
        )
        self._append(event)

    def record_pre_model(
        self,
        event_name: str,
        cache_key: str,
        question: str,
        packing: Any,
        slots: list[dict[str, str]],
        *,
        reason: str,
    ) -> None:
        if not self.enabled:
            return
        event = self._base_event(event_name, cache_key, question, packing, slots)
        event["outcome"] = {"status": event_name, "reason": reason}
        event_index = self._append(event)
        if cache_key:
            self.cache_event_indices[cache_key] = event_index

    def snapshot(self) -> dict[str, Any] | None:
        if not self.enabled:
            return None
        return {
            "contract_id": SEMANTIC_PROPOSITION_DEBUG_CONTRACT,
            "event_count": self.event_count,
            "dropped_event_count": self.dropped_event_count,
            "events": deepcopy(self.events),
        }

    def _base_event(
        self,
        event_name: str,
        cache_key: str,
        question: str,
        packing: Any,
        slots: list[dict[str, str]],
    ) -> dict[str, Any]:
        return {
            "event": event_name,
            "cache_key": cache_key,
            "semantic_pack_digest": str(
                getattr(packing, "semantic_pack_digest", "") or ""
            ),
            "question_proposition": deepcopy(
                getattr(packing, "question_proposition", {}) or {}
            ),
            "question_proposition_resolution": deepcopy(
                getattr(packing, "question_proposition_resolution", {}) or {}
            ),
            "route_evidence_signature": [
                value["evidence_id"] for value in packing.records
            ],
            "question": question,
            "required_slots": deepcopy(slots),
            "packed_evidence": deepcopy(packing.records),
        }

    def _append(self, event: dict[str, Any]) -> int:
        self.event_count += 1
        event["event_index"] = self.event_count
        self.events.append(event)
        if len(self.events) > SEMANTIC_PROPOSITION_DEBUG_MAX_EVENTS:
            self.events.pop(0)
            self.dropped_event_count += 1
        return self.event_count


def response_text(response: Any) -> str:
    return str(
        getattr(response, "text", "") or getattr(response, "content", "") or response
    )


def response_completion_tokens(response: Any | None) -> int:
    value = getattr(response, "completion_tokens", -1) if response is not None else -1
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def response_finish_reason(response: Any | None) -> str:
    if response is None:
        return ""
    for key in ("additional_kwargs", "response_metadata"):
        metadata = getattr(response, key, None)
        if isinstance(metadata, dict):
            reason = str(metadata.get("finish_reason") or "").strip()
            if reason:
                return reason
    return str(getattr(response, "finish_reason", "") or "").strip()


def provider_failure(exc: Exception) -> tuple[str, str]:
    message = str(exc)
    normalized = message.casefold()
    if (
        "maximum context length" in normalized
        or "context length exceeded" in normalized
    ):
        reason = "provider_context_length_exceeded"
    elif "grammar error" in normalized or "unimplemented keys" in normalized:
        reason = "provider_response_schema_unsupported"
    else:
        reason = "provider_call_failed"
    return reason, message[:4000]


def _stage_debug(stage: Any) -> dict[str, Any]:
    return {
        "status": _stage_status(stage),
        "call_count": stage.call_count,
        "retry_count": stage.retry_count,
        "failure_reason": stage.provider_failure_reason or stage.failure_reason,
        "attempts": [
            {
                "attempt": index,
                "correction_reason": attempt.correction_reason,
                "provider_failure_reason": attempt.provider_failure_reason,
                "provider_failure_detail": attempt.provider_failure_detail,
                "parse_failure_reason": attempt.parse_failure_reason,
                "finish_reason": response_finish_reason(attempt.response),
                "completion_tokens": response_completion_tokens(attempt.response),
                "raw_response": _bounded_response_text(attempt.response),
                "raw_response_truncated": _response_text_exceeds_bound(
                    attempt.response
                ),
                "parsed_value": deepcopy(attempt.parsed_value),
            }
            for index, attempt in enumerate(stage.attempts, start=1)
        ],
    }


def _stage_status(stage: Any) -> str:
    if stage.provider_failure_reason:
        return "provider_failed"
    return "parsed" if stage.value is not None else "parse_failed"


def _bounded_response_text(response: Any | None) -> str:
    if response is None:
        return ""
    return response_text(response)[:SEMANTIC_PROPOSITION_DEBUG_RESPONSE_CHARS]


def _response_text_exceeds_bound(response: Any | None) -> bool:
    return bool(
        response is not None
        and len(response_text(response)) > SEMANTIC_PROPOSITION_DEBUG_RESPONSE_CHARS
    )


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}
