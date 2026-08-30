from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable

from .mara_semantic_proposition_debug import SemanticPropositionStageAttempt


@dataclass(frozen=True)
class StageCallResult:
    response: Any | None
    failure_reason: str = ""
    failure_detail: str = ""
    provider_call_started: bool = True
    request_snapshot: dict[str, Any] | None = None


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


def parsed_stage(
    call: Callable[[str], StageCallResult],
    parse: Callable[[Any], Any],
    *,
    semantic_identity: Callable[[Any, Any], Any] | None = None,
    identity_failure_reason: str = "semantic_retry_identity_changed",
    max_parse_retries: int = 1,
) -> ParsedSemanticStage:
    initial_call = call("")
    response = initial_call.response
    if response is None:
        return _failed_stage(initial_call)
    parsed = parse(response)
    attempts = [_stage_attempt(response, parsed, "", initial_call.request_snapshot)]
    initial_failure = str(parsed.failure_reason or "")
    initial_identity = (
        semantic_identity(response, parsed) if semantic_identity is not None else None
    )
    if parsed.value is not None or not max_parse_retries:
        return _parsed_result(response, parsed, initial_failure, 0, attempts)
    retry_call = call(parsed.failure_reason)
    response = retry_call.response
    if response is None:
        return _retry_failed_stage(
            initial_failure,
            retry_call,
            attempts,
        )
    parsed = parse(response)
    attempts.append(
        _stage_attempt(
            response,
            parsed,
            initial_failure,
            retry_call.request_snapshot,
        )
    )
    retry_identity = (
        semantic_identity(response, parsed) if semantic_identity is not None else None
    )
    if (
        initial_identity is not None
        and retry_identity is not None
        and retry_identity != initial_identity
    ):
        return ParsedSemanticStage(
            response,
            None,
            identity_failure_reason,
            initial_failure,
            1,
            "",
            2,
            tuple(attempts),
        )
    return _parsed_result(response, parsed, initial_failure, 1, attempts)


def _failed_stage(call: StageCallResult) -> ParsedSemanticStage:
    provider_failure_reason = call.failure_reason if call.provider_call_started else ""
    parse_failure_reason = "" if call.provider_call_started else call.failure_reason
    attempt = _failed_attempt(call, correction="")
    return ParsedSemanticStage(
        None,
        None,
        parse_failure_reason,
        parse_failure_reason,
        0,
        provider_failure_reason,
        int(call.provider_call_started),
        (attempt,),
    )


def _retry_failed_stage(
    initial_failure: str,
    call: StageCallResult,
    attempts: list[SemanticPropositionStageAttempt],
) -> ParsedSemanticStage:
    provider_failure_reason = call.failure_reason if call.provider_call_started else ""
    parse_failure_reason = "" if call.provider_call_started else call.failure_reason
    attempts.append(
        _failed_attempt(
            call,
            correction=initial_failure,
        )
    )
    return ParsedSemanticStage(
        None,
        None,
        parse_failure_reason,
        initial_failure,
        1,
        provider_failure_reason,
        1 + int(call.provider_call_started),
        tuple(attempts),
    )


def _failed_attempt(
    call: StageCallResult,
    *,
    correction: str,
) -> SemanticPropositionStageAttempt:
    provider_failure_reason = call.failure_reason if call.provider_call_started else ""
    parse_failure_reason = "" if call.provider_call_started else call.failure_reason
    return SemanticPropositionStageAttempt(
        None,
        None,
        correction,
        parse_failure_reason,
        provider_failure_reason,
        call.failure_detail if call.provider_call_started else "",
        call.request_snapshot,
    )


def _stage_attempt(
    response: Any,
    parsed: Any,
    correction: str,
    request_snapshot: dict[str, Any] | None,
) -> SemanticPropositionStageAttempt:
    return SemanticPropositionStageAttempt(
        response,
        deepcopy(parsed.value),
        correction,
        str(parsed.failure_reason or ""),
        "",
        "",
        request_snapshot,
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
