from __future__ import annotations

import logging
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable

from ktem.docqa.boolean_authority_schema import SEMANTIC_ENTAILMENT_AUDIT_CONTRACT

from kotaemon.base import HumanMessage, SystemMessage

from .mara_semantic_entailment_audit import (
    SEMANTIC_ENTAILMENT_AUDIT_MAX_TOKENS,
    SEMANTIC_ENTAILMENT_AUDIT_SYSTEM_PROMPT,
    parse_semantic_entailment_audit,
    semantic_entailment_audit_response_format,
)
from .mara_semantic_proposition_debug import SemanticPropositionStageAttempt
from .mara_semantic_proposition_debug import provider_failure
from .mara_semantic_proposition_debug import response_completion_tokens
from .mara_semantic_proposition_debug import response_finish_reason
from .mara_semantic_proposition_debug import response_text
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
class ParsedSemanticStage:
    response: Any | None
    value: dict[str, Any] | None
    failure_reason: str
    initial_failure_reason: str
    retry_count: int
    provider_failure_reason: str
    call_count: int
    attempts: tuple[SemanticPropositionStageAttempt, ...]


def proposal_stage(
    llm: Any,
    prompt: str,
    *,
    packed: list[dict[str, Any]],
    slots: list[dict[str, str]],
    model: str,
    seed: int,
) -> ParsedSemanticStage:
    def call(correction: str = "") -> tuple[Any | None, str, str]:
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
            response_text(response),
            packed=packed,
            slot_ids={value["slot_id"] for value in slots},
            model=model,
            seed=seed,
        )

    return _parsed_stage(call, parse)


def audit_stage(
    llm: Any,
    prompt: str,
    premise_count: int,
    *,
    seed: int,
) -> ParsedSemanticStage:
    labels = [f"P{index}" for index in range(1, premise_count + 1)]

    def call(correction: str = "") -> tuple[Any | None, str, str]:
        return _call_audit(
            llm,
            prompt,
            premise_labels=labels,
            seed=seed,
            correction_reason=correction,
        )

    def parse(response: Any) -> Any:
        return parse_semantic_entailment_audit(
            response_text(response),
            premise_labels=labels,
        )

    return _parsed_stage(call, parse)


def proposal_diagnostics(stage: ParsedSemanticStage) -> dict[str, Any]:
    return {
        "proposal_retry_count": stage.retry_count,
        "initial_parse_failure_reason": stage.initial_failure_reason,
        "parse_failure_reason": stage.failure_reason,
        "response_finish_reason": response_finish_reason(stage.response),
        "response_completion_tokens": response_completion_tokens(stage.response),
        "response_chars": (
            len(response_text(stage.response)) if stage.response is not None else 0
        ),
        "audit_status": "not_started",
        "audit_reason": "",
    }


def audit_diagnostics(stage: ParsedSemanticStage, *, model: str) -> dict[str, Any]:
    return {
        "audit_contract_id": SEMANTIC_ENTAILMENT_AUDIT_CONTRACT,
        "audit_model": model,
        "audit_status": "failed" if stage.value is None else "parsed",
        "audit_reason": stage.provider_failure_reason,
        "audit_retry_count": stage.retry_count,
        "audit_initial_parse_failure_reason": stage.initial_failure_reason,
        "audit_parse_failure_reason": stage.failure_reason,
        "audit_response_finish_reason": response_finish_reason(stage.response),
        "audit_response_completion_tokens": response_completion_tokens(stage.response),
        "audit_response_chars": (
            len(response_text(stage.response)) if stage.response is not None else 0
        ),
    }


def invalid_response_reason(
    response: Any,
    *,
    max_tokens: int,
    invalid_reason: str,
) -> str:
    finish_reason = response_finish_reason(response).casefold()
    completion_tokens = response_completion_tokens(response)
    if finish_reason in {"length", "max_tokens"} or completion_tokens >= max_tokens:
        return (
            "semantic_entailment_audit_output_truncated"
            if invalid_reason == "invalid_entailment_audit_json"
            else "provider_output_truncated"
        )
    return invalid_reason


def _parsed_stage(
    call: Callable[[str], tuple[Any | None, str, str]],
    parse: Callable[[Any], Any],
) -> ParsedSemanticStage:
    response, failure, detail = call("")
    if response is None:
        attempt = SemanticPropositionStageAttempt(None, None, "", "", failure, detail)
        return ParsedSemanticStage(None, None, "", "", 0, failure, 1, (attempt,))
    parsed = parse(response)
    attempts = [_stage_attempt(response, parsed, "")]
    initial_failure = str(parsed.failure_reason or "")
    if parsed.value is not None or not SEMANTIC_PROPOSITION_VERIFIER_MAX_PARSE_RETRIES:
        return _parsed_result(response, parsed, initial_failure, 0, attempts)
    response, failure, detail = call(parsed.failure_reason)
    if response is None:
        attempts.append(
            SemanticPropositionStageAttempt(
                None, None, initial_failure, "", failure, detail
            )
        )
        return ParsedSemanticStage(
            None, None, "", initial_failure, 1, failure, 2, tuple(attempts)
        )
    parsed = parse(response)
    attempts.append(_stage_attempt(response, parsed, initial_failure))
    return _parsed_result(response, parsed, initial_failure, 1, attempts)


def _stage_attempt(response: Any, parsed: Any, correction: str) -> SemanticPropositionStageAttempt:
    return SemanticPropositionStageAttempt(
        response,
        deepcopy(parsed.value),
        correction,
        str(parsed.failure_reason or ""),
        "",
        "",
    )


def _parsed_result(
    response: Any,
    parsed: Any,
    initial_failure: str,
    retry_count: int,
    attempts: list[SemanticPropositionStageAttempt],
) -> ParsedSemanticStage:
    return ParsedSemanticStage(
        response,
        parsed.value,
        str(parsed.failure_reason or ""),
        initial_failure,
        retry_count,
        "",
        1 + retry_count,
        tuple(attempts),
    )


def _call_proposal(
    llm: Any,
    prompt: str,
    *,
    packed: list[dict[str, Any]],
    slots: list[dict[str, str]],
    seed: int,
    correction_reason: str,
) -> tuple[Any | None, str, str]:
    try:
        return (
            llm(
                [
                    SystemMessage(content=SEMANTIC_PROPOSITION_VERIFIER_SYSTEM_PROMPT),
                    HumanMessage(content=_corrected_prompt(prompt, correction_reason)),
                ],
                max_tokens=SEMANTIC_PROPOSITION_VERIFIER_MAX_TOKENS,
                response_format=semantic_proposition_response_format(
                    [], [value["slot_id"] for value in slots]
                ),
                temperature=0,
                top_p=1,
                seed=seed,
            ),
            "",
            "",
        )
    except Exception as exc:
        LOGGER.exception("Semantic proposition verifier model call failed")
        return None, *provider_failure(exc)


def _call_audit(
    llm: Any,
    prompt: str,
    *,
    premise_labels: list[str],
    seed: int,
    correction_reason: str,
) -> tuple[Any | None, str, str]:
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
            "",
        )
    except Exception as exc:
        LOGGER.exception("Semantic entailment audit model call failed")
        return None, *provider_failure(exc)


def _corrected_prompt(prompt: str, failure_reason: str) -> str:
    if not failure_reason:
        return prompt
    return (
        f"{prompt}\n\nYour previous response was rejected by the local parser "
        f"({failure_reason}). Return one complete object that follows every "
        "schema and cross-field requirement."
    )
