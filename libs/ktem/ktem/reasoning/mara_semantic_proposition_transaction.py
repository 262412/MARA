from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from ktem.docqa.boolean_authority_schema import (
    GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
    SEMANTIC_ENTAILMENT_AUDIT_CONTRACT,
    SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
)
from ktem.docqa.semantic_entailment_audit import semantic_entailment_audit_attestation

from kotaemon.base import HumanMessage, SystemMessage

from .mara_semantic_entailment_audit import (
    SEMANTIC_ENTAILMENT_AUDIT_MAX_TOKENS,
    SEMANTIC_ENTAILMENT_AUDIT_SYSTEM_PROMPT,
    parse_semantic_entailment_audit,
    semantic_entailment_audit_prompt,
    semantic_entailment_audit_response_format,
    semantic_entailment_rejection_reason,
)
from .mara_semantic_proposition_packing import (
    SEMANTIC_PROPOSITION_VERIFIER_SYSTEM_PROMPT,
)
from .mara_semantic_proposition_schema import (
    parse_semantic_proposition_response,
    semantic_proposition_response_format,
)

SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS = 768
SEMANTIC_PROPOSITION_VERIFIER_MAX_PARSE_RETRIES = 1

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class SemanticPropositionTransactionResult:
    value: dict[str, Any] | None
    status: str
    reason: str
    diagnostics: dict[str, Any]
    proposal_call_count: int
    audit_call_count: int


@dataclass(frozen=True)
class _ParsedStage:
    response: Any | None
    value: dict[str, Any] | None
    failure_reason: str
    initial_failure_reason: str
    retry_count: int
    provider_failure_reason: str
    call_count: int


def run_semantic_proposition_transaction(
    proposal_llm: Any,
    audit_llm: Any,
    prompt: str,
    *,
    question: str,
    packed: list[dict[str, str]],
    slots: list[dict[str, str]],
    proposal_model: str,
    audit_model: str,
    seed: int,
) -> SemanticPropositionTransactionResult:
    proposal = _proposal_stage(
        proposal_llm,
        prompt,
        packed=packed,
        slots=slots,
        model=proposal_model,
        seed=seed,
    )
    diagnostics = _proposal_diagnostics(proposal)
    if proposal.provider_failure_reason:
        return _result(
            None,
            "failed",
            proposal.provider_failure_reason,
            diagnostics,
            proposal_calls=proposal.call_count,
        )
    if proposal.value is None:
        reason = _invalid_response_reason(
            proposal.response,
            max_tokens=SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS,
            invalid_reason="invalid_model_json",
        )
        return _result(
            None,
            "failed",
            reason,
            diagnostics,
            proposal_calls=proposal.call_count,
        )
    if proposal.value["verdict"] == "insufficient_evidence":
        diagnostics.update({"audit_status": "not_required", "audit_reason": ""})
        return _result(
            proposal.value,
            "parsed",
            "strict_schema_parsed",
            diagnostics,
            proposal_calls=proposal.call_count,
        )
    return _audit_transaction(
        audit_llm,
        question,
        proposal,
        diagnostics,
        proposal_model=proposal_model,
        audit_model=audit_model,
        seed=seed,
    )


def insufficient_semantic_result(model: str, seed: int) -> dict[str, Any]:
    return {
        "contract_id": SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
        "verdict": "insufficient_evidence",
        "support_mode": "evidence_set",
        "jointly_complete": False,
        "each_premise_required": False,
        "premises": [],
        "verifier": {
            "contract_id": GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
            "model": model,
            "seed": seed,
        },
    }


def _proposal_stage(
    llm: Any,
    prompt: str,
    *,
    packed: list[dict[str, str]],
    slots: list[dict[str, str]],
    model: str,
    seed: int,
) -> _ParsedStage:
    def call(correction: str = "") -> tuple[Any | None, str]:
        return _call_proposal(
            llm,
            prompt,
            packed=packed,
            slots=slots,
            seed=seed,
            correction_reason=correction,
        )

    def parse(response: Any) -> Any:
        return parse_semantic_proposition_response(
            _response_text(response),
            packed=packed,
            slot_ids={value["slot_id"] for value in slots},
            model=model,
            seed=seed,
        )

    return _parsed_stage(call, parse)


def _audit_transaction(
    audit_llm: Any,
    question: str,
    proposal: _ParsedStage,
    diagnostics: dict[str, Any],
    *,
    proposal_model: str,
    audit_model: str,
    seed: int,
) -> SemanticPropositionTransactionResult:
    value = proposal.value or {}
    premises = value.get("premises") or []
    try:
        prompt = semantic_entailment_audit_prompt(
            question,
            str(value.get("verdict") or ""),
            premises,
        )
    except ValueError:
        diagnostics.update(
            {"audit_status": "failed", "audit_reason": "audit_prompt_bound_exceeded"}
        )
        return _result(
            None,
            "failed",
            "audit_prompt_bound_exceeded",
            diagnostics,
            proposal_calls=proposal.call_count,
        )
    audit = _audit_stage(audit_llm, prompt, len(premises), seed=seed + 1)
    diagnostics.update(_audit_diagnostics(audit, model=audit_model))
    return _audit_result(
        question,
        proposal,
        audit,
        diagnostics,
        proposal_model=proposal_model,
        audit_model=audit_model,
        seed=seed,
    )


def _audit_stage(
    llm: Any,
    prompt: str,
    premise_count: int,
    *,
    seed: int,
) -> _ParsedStage:
    labels = [f"P{index}" for index in range(1, premise_count + 1)]

    def call(correction: str = "") -> tuple[Any | None, str]:
        return _call_audit(
            llm,
            prompt,
            premise_labels=labels,
            seed=seed,
            correction_reason=correction,
        )

    def parse(response: Any) -> Any:
        return parse_semantic_entailment_audit(
            _response_text(response),
            premise_labels=labels,
        )

    return _parsed_stage(call, parse)


def _parsed_stage(
    call: Callable[[str], tuple[Any | None, str]],
    parse: Callable[[Any], Any],
) -> _ParsedStage:
    response, provider_failure = call("")
    if response is None:
        return _ParsedStage(None, None, "", "", 0, provider_failure, 1)
    parsed = parse(response)
    initial_failure = str(parsed.failure_reason or "")
    retry_count = 0
    if parsed.value is None and SEMANTIC_PROPOSITION_VERIFIER_MAX_PARSE_RETRIES:
        retry_count = 1
        response, provider_failure = call(parsed.failure_reason)
        if response is None:
            return _ParsedStage(
                None,
                None,
                "",
                initial_failure,
                retry_count,
                provider_failure,
                2,
            )
        parsed = parse(response)
    return _ParsedStage(
        response,
        parsed.value,
        str(parsed.failure_reason or ""),
        initial_failure,
        retry_count,
        "",
        1 + retry_count,
    )


def _audit_result(
    question: str,
    proposal: _ParsedStage,
    audit: _ParsedStage,
    diagnostics: dict[str, Any],
    *,
    proposal_model: str,
    audit_model: str,
    seed: int,
) -> SemanticPropositionTransactionResult:
    if audit.provider_failure_reason:
        return _result(
            None,
            "failed",
            audit.provider_failure_reason,
            diagnostics,
            proposal_calls=proposal.call_count,
            audit_calls=audit.call_count,
        )
    if audit.value is None:
        reason = _invalid_response_reason(
            audit.response,
            max_tokens=SEMANTIC_ENTAILMENT_AUDIT_MAX_TOKENS,
            invalid_reason="invalid_entailment_audit_json",
        )
        diagnostics["audit_reason"] = reason
        return _result(
            None,
            "failed",
            reason,
            diagnostics,
            proposal_calls=proposal.call_count,
            audit_calls=audit.call_count,
        )
    rejection_reason = semantic_entailment_rejection_reason(audit.value)
    if rejection_reason:
        diagnostics.update(
            {"audit_status": "rejected", "audit_reason": rejection_reason}
        )
        return _result(
            insufficient_semantic_result(proposal_model, seed),
            "audit_rejected",
            "semantic_entailment_audit_rejected",
            diagnostics,
            proposal_calls=proposal.call_count,
            audit_calls=audit.call_count,
        )
    value = proposal.value or {}
    value["entailment_audit"] = semantic_entailment_audit_attestation(
        question,
        value["verdict"],
        value["premises"],
        model=audit_model,
        seed=seed + 1,
    )
    diagnostics.update(
        {
            "audit_status": "verified",
            "audit_reason": "",
            "audit_proposal_digest": value["entailment_audit"]["proposal_digest"],
        }
    )
    return _result(
        value,
        "parsed",
        "strict_schema_and_entailment_audit",
        diagnostics,
        proposal_calls=proposal.call_count,
        audit_calls=audit.call_count,
    )


def _call_proposal(
    llm: Any,
    prompt: str,
    *,
    packed: list[dict[str, str]],
    slots: list[dict[str, str]],
    seed: int,
    correction_reason: str,
) -> tuple[Any | None, str]:
    try:
        return (
            llm(
                [
                    SystemMessage(content=SEMANTIC_PROPOSITION_VERIFIER_SYSTEM_PROMPT),
                    HumanMessage(content=_corrected_prompt(prompt, correction_reason)),
                ],
                max_tokens=SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS,
                response_format=semantic_proposition_response_format(
                    [value["label"] for value in packed],
                    [value["slot_id"] for value in slots],
                ),
                temperature=0,
                top_p=1,
                seed=seed,
            ),
            "",
        )
    except Exception as exc:
        LOGGER.exception("Semantic proposition verifier model call failed")
        return None, _provider_failure_reason(exc)


def _call_audit(
    llm: Any,
    prompt: str,
    *,
    premise_labels: list[str],
    seed: int,
    correction_reason: str,
) -> tuple[Any | None, str]:
    try:
        return (
            llm(
                [
                    SystemMessage(content=SEMANTIC_ENTAILMENT_AUDIT_SYSTEM_PROMPT),
                    HumanMessage(content=_corrected_prompt(prompt, correction_reason)),
                ],
                max_tokens=SEMANTIC_ENTAILMENT_AUDIT_MAX_TOKENS,
                response_format=semantic_entailment_audit_response_format(
                    premise_labels
                ),
                temperature=0,
                top_p=1,
                seed=seed,
            ),
            "",
        )
    except Exception as exc:
        LOGGER.exception("Semantic entailment audit model call failed")
        return None, _provider_failure_reason(exc)


def _proposal_diagnostics(stage: _ParsedStage) -> dict[str, Any]:
    return {
        "proposal_retry_count": stage.retry_count,
        "initial_parse_failure_reason": stage.initial_failure_reason,
        "parse_failure_reason": stage.failure_reason,
        "response_finish_reason": _response_finish_reason(stage.response),
        "response_completion_tokens": _response_completion_tokens(stage.response),
        "response_chars": (
            len(_response_text(stage.response)) if stage.response is not None else 0
        ),
        "audit_status": "not_started",
        "audit_reason": "",
    }


def _audit_diagnostics(stage: _ParsedStage, *, model: str) -> dict[str, Any]:
    return {
        "audit_contract_id": SEMANTIC_ENTAILMENT_AUDIT_CONTRACT,
        "audit_model": model,
        "audit_status": "failed" if stage.value is None else "parsed",
        "audit_reason": stage.provider_failure_reason,
        "audit_retry_count": stage.retry_count,
        "audit_initial_parse_failure_reason": stage.initial_failure_reason,
        "audit_parse_failure_reason": stage.failure_reason,
        "audit_response_finish_reason": _response_finish_reason(stage.response),
        "audit_response_completion_tokens": _response_completion_tokens(stage.response),
        "audit_response_chars": (
            len(_response_text(stage.response)) if stage.response is not None else 0
        ),
    }


def _result(
    value: dict[str, Any] | None,
    status: str,
    reason: str,
    diagnostics: dict[str, Any],
    *,
    proposal_calls: int,
    audit_calls: int = 0,
) -> SemanticPropositionTransactionResult:
    return SemanticPropositionTransactionResult(
        value=value,
        status=status,
        reason=reason,
        diagnostics=diagnostics,
        proposal_call_count=proposal_calls,
        audit_call_count=audit_calls,
    )


def _corrected_prompt(prompt: str, failure_reason: str) -> str:
    if not failure_reason:
        return prompt
    return (
        f"{prompt}\n\nYour previous response was rejected by the local parser "
        f"({failure_reason}). Return one complete object that follows every "
        "schema and cross-field requirement."
    )


def _provider_failure_reason(exc: Exception) -> str:
    message = str(exc).casefold()
    if "maximum context length" in message or "context length exceeded" in message:
        return "provider_context_length_exceeded"
    if "grammar error" in message or "unimplemented keys" in message:
        return "provider_response_schema_unsupported"
    return "provider_call_failed"


def _invalid_response_reason(
    response: Any,
    *,
    max_tokens: int,
    invalid_reason: str,
) -> str:
    finish_reason = _response_finish_reason(response).casefold()
    completion_tokens = _response_completion_tokens(response)
    if finish_reason in {"length", "max_tokens"} or completion_tokens >= max_tokens:
        return (
            "semantic_entailment_audit_output_truncated"
            if invalid_reason == "invalid_entailment_audit_json"
            else "provider_output_truncated"
        )
    return invalid_reason


def _response_text(response: Any) -> str:
    return str(
        getattr(response, "text", "") or getattr(response, "content", "") or response
    )


def _response_completion_tokens(response: Any | None) -> int:
    value = getattr(response, "completion_tokens", -1) if response is not None else -1
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def _response_finish_reason(response: Any | None) -> str:
    if response is None:
        return ""
    for key in ("additional_kwargs", "response_metadata"):
        metadata = getattr(response, key, None)
        if isinstance(metadata, dict):
            reason = str(metadata.get("finish_reason") or "").strip()
            if reason:
                return reason
    return str(getattr(response, "finish_reason", "") or "").strip()
