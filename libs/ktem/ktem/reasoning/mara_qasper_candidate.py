from __future__ import annotations

import json
import logging
from copy import deepcopy
from typing import Any

from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.query_planning import request_planning_question

from kotaemon.base import HumanMessage, SystemMessage

from .mara_answer_type_contract import request_answer_type
from .mara_qasper_candidate_evidence import (  # noqa: F401
    candidate_selector_options as _candidate_selector_options,
)
from .mara_qasper_candidate_identity import candidate_digest as _digest
from .mara_qasper_candidate_identity import candidate_model_name as _model_name
from .mara_qasper_candidate_identity import (
    candidate_transaction_identity as _transaction_identity,
)
from .mara_qasper_candidate_identity import effective_candidate_seed
from .mara_qasper_candidate_prompt import (
    _bound_candidate_slots as _prompt_bound_candidate_slots,
)
from .mara_qasper_candidate_prompt import _candidate_evidence, _candidate_prompt
from .mara_qasper_candidate_budget import (
    QASPER_CANDIDATE_INPUT_TOKEN_BUDGET,
    QASPER_CANDIDATE_MAX_MODEL_LEN,  # noqa: F401
    QASPER_CANDIDATE_MAX_TOKENS,
    QASPER_CANDIDATE_TOKEN_HEADROOM,  # noqa: F401
    candidate_drop_index as _candidate_drop_index,
    candidate_generation_trace as _candidate_generation_trace,
    candidate_input_token_measurement,
    estimate_qasper_candidate_input_tokens,  # noqa: F401
)
from .mara_semantic_proposition_debug import (
    provider_failure,
    response_completion_tokens,
    response_finish_reason,
    response_text,
)

QASPER_CANDIDATE_GENERATION_CONTRACT = "qasper_typed_candidate_generation.v2"
QASPER_CANDIDATE_RESPONSE_CONTRACT = "qasper_typed_candidate.v1"
QASPER_CANDIDATES = {"yes", "no", "unanswerable"}
QASPER_CANDIDATE_MAX_RESPONSE_CHARS = 16_000
QASPER_CANDIDATE_DEFAULT_SEED = 20260724

LOGGER = logging.getLogger(__name__)

# Preserve the existing private test/debug seam after moving prompt construction.
_bound_candidate_slots = _prompt_bound_candidate_slots

_SYSTEM_PROMPT = (
    "You are the sole answer-candidate generator for a QASPER Boolean question. "
    "Use only the typed question proposition and labeled retrieved evidence. "
    "Return exactly one structured "
    "candidate: yes, no, or unanswerable. Prefer proposition- and slot-aligned "
    "evidence when deciding the candidate: use yes for proposition support, no "
    "for an explicit contradiction, and unanswerable only when neither is present. "
    "Candidate parsing is format-only; "
    "verification uncertainty is handled later by the verifier. Do not "
    "include explanation, citations, or an alternative answer."
)

_CONTRACT_PROBE_SYSTEM_PROMPT = (
    "You are exercising the QASPER candidate transport contract. Preserve the "
    "supplied original candidate exactly. Do not answer the question or change "
    "the candidate after reading the audit context. Return only the required "
    "structured candidate object."
)


def qasper_typed_candidate_request(request: Any) -> bool:
    domain = str(getattr(request, "verification_domain", "") or "").casefold()
    origin = str(getattr(request, "origin", "") or "").casefold()
    return (
        origin == "benchmark"
        and (domain == "qasper" or domain.startswith("qasper_"))
        and request_answer_type(request) == "boolean"
    )


def generate_qasper_typed_candidate(
    pipeline: Any,
    request: Any,
    bundle: EvidenceBundle,
) -> str:
    llm = _answering_llm(pipeline)
    question = request_planning_question(request)
    evidence, evidence_diagnostics = _candidate_evidence(
        request,
        question,
        bundle,
    )
    seed = effective_candidate_seed(
        request,
        default_seed=QASPER_CANDIDATE_DEFAULT_SEED,
    )
    route = str(bundle.route or "")
    controlled_candidate = _contract_probe_original_candidate(request, route)
    identity = _transaction_identity(request, route, seed)
    response_schema = qasper_candidate_response_format()
    (
        evidence,
        evidence_diagnostics,
        messages,
        token_measurement,
        request_dropped_count,
    ) = _fit_candidate_request(
        llm,
        question,
        evidence,
        evidence_diagnostics,
        response_schema=response_schema,
        controlled_candidate=controlled_candidate,
    )
    serialized_messages = _serialized_messages(messages)
    schema_digest = _digest(response_schema)
    input_digest = _digest(
        {
            "messages": serialized_messages,
            "response_schema_digest": schema_digest,
            "seed": seed,
            "route": route,
            "benchmark_route_id": identity.get("benchmark_route_id", ""),
        }
    )
    trace = _candidate_generation_trace(
        model=_model_name(llm),
        identity=identity,
        route=route,
        seed=seed,
        serialized_messages=serialized_messages,
        input_digest=input_digest,
        evidence=evidence,
        evidence_diagnostics=evidence_diagnostics,
        controlled_candidate=controlled_candidate,
        response_schema_digest=schema_digest,
        token_measurement=token_measurement,
        request_dropped_count=request_dropped_count,
    )
    bundle.metadata["qasper_candidate_generation"] = trace
    if not _candidate_request_ready(llm, token_measurement, trace, identity):
        return ""
    return _generate_candidate_response(
        llm,
        messages,
        trace,
        identity,
        input_digest,
        seed,
        response_schema,
    )


def _candidate_request_ready(
    llm: Any | None,
    token_measurement: dict[str, Any],
    trace: dict[str, Any],
    identity: dict[str, str],
) -> bool:
    if llm is None:
        trace.update(status="failed", failure_reason="generator_llm_unavailable")
        return False
    if token_measurement.get("tokenizer_failed"):
        failure_detail = (
            "tokenizer_endpoint="
            f"{token_measurement.get('tokenizer_endpoint', '')}; "
            "tokenizer_method="
            f"{token_measurement.get('tokenizer_method', '')}; "
            "tokenizer_failure_reason="
            f"{token_measurement.get('tokenizer_failure_reason', '')}"
        )
        trace.update(
            status="failed",
            failure_reason="provider_tokenizer_failed",
            provider_failure_reason="provider_tokenizer_failed",
            provider_failure_detail=failure_detail,
        )
        trace["attempts"] = [
            {
                "attempt_id": identity["attempt_id"],
                "status": "provider_failed",
                "failure_reason": "provider_tokenizer_failed",
                "failure_detail": failure_detail,
            }
        ]
        return False
    if (
        token_measurement["estimated_input_tokens"]
        > QASPER_CANDIDATE_INPUT_TOKEN_BUDGET
    ):
        trace.update(status="failed", failure_reason="candidate_input_budget_exceeded")
        return False
    return True


def _candidate_messages(
    question: str,
    evidence: list[dict[str, Any]],
    evidence_diagnostics: dict[str, Any],
    *,
    controlled_candidate: str,
) -> list[Any]:
    audit_context = _candidate_prompt(
        question,
        evidence,
        proposition=evidence_diagnostics.get("typed_proposition"),
        proposition_resolution=evidence_diagnostics.get(
            "question_proposition_resolution"
        ),
        required_slots=evidence_diagnostics.get("required_slots", []),
    )
    if not controlled_candidate:
        return [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=audit_context),
        ]
    return [
        SystemMessage(content=_CONTRACT_PROBE_SYSTEM_PROMPT),
        HumanMessage(
            content=(
                "/no_think\nCONTROLLED ORIGINAL CANDIDATE UNDER AUDIT:\n"
                f"{controlled_candidate}\n\nAUDIT CONTEXT (DO NOT RE-ANSWER):\n"
                f"{audit_context}"
            )
        ),
    ]


def _fit_candidate_request(
    llm: Any | None,
    question: str,
    evidence: list[dict[str, Any]],
    evidence_diagnostics: dict[str, Any],
    *,
    response_schema: dict[str, Any],
    controlled_candidate: str,
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
    list[Any],
    dict[str, Any],
    int,
]:
    selected = list(evidence)
    dropped_count = 0
    while True:
        bound_slots = _bound_candidate_slots(
            evidence_diagnostics.get("required_slots", []), selected
        )
        diagnostics = {
            **evidence_diagnostics,
            "required_slots": bound_slots,
            "candidate_request_dropped_evidence_count": dropped_count,
            "evidence_dropped_count": (
                int(evidence_diagnostics.get("evidence_dropped_count") or 0)
                + dropped_count
            ),
        }
        messages = _candidate_messages(
            question,
            selected,
            diagnostics,
            controlled_candidate=controlled_candidate,
        )
        token_measurement = candidate_input_token_measurement(
            llm,
            messages,
            response_schema,
        )
        if token_measurement.get("tokenizer_failed"):
            return (
                selected,
                diagnostics,
                messages,
                token_measurement,
                dropped_count,
            )
        if (
            token_measurement["estimated_input_tokens"]
            <= QASPER_CANDIDATE_INPUT_TOKEN_BUDGET
            or not selected
        ):
            return (
                selected,
                diagnostics,
                messages,
                token_measurement,
                dropped_count,
            )
        drop_index = _candidate_drop_index(selected)
        if drop_index is None:
            return (
                selected,
                diagnostics,
                messages,
                token_measurement,
                dropped_count,
            )
        selected.pop(drop_index)
        dropped_count += 1


def _contract_probe_original_candidate(request: Any, route: str) -> str:
    trace_context = getattr(request, "trace_context", None)
    trace_context = trace_context if isinstance(trace_context, dict) else {}
    if "contract_probe_original_candidate" not in trace_context:
        return ""
    candidate = (
        str(trace_context.get("contract_probe_original_candidate") or "")
        .strip()
        .casefold()
    )
    eligible = bool(
        route == "contract_probe"
        and str(getattr(request, "origin", "") or "").casefold() == "benchmark"
        and str(getattr(request, "verification_domain", "") or "").casefold()
        == "qasper"
    )
    if not eligible or candidate not in QASPER_CANDIDATES:
        raise ValueError("invalid controlled QASPER contract-probe candidate")
    return candidate


def _generate_candidate_response(
    llm: Any,
    messages: list[Any],
    trace: dict[str, Any],
    identity: dict[str, str],
    input_digest: str,
    seed: int,
    response_schema: dict[str, Any],
) -> str:
    try:
        response = llm(
            messages,
            max_tokens=QASPER_CANDIDATE_MAX_TOKENS,
            response_format=response_schema,
            temperature=0,
            top_p=1,
            seed=seed,
        )
    except Exception as exc:
        LOGGER.exception("QASPER typed candidate generation failed")
        reason, detail = provider_failure(exc)
        trace.update(
            status="failed",
            failure_reason=reason,
            provider_failure_reason=reason,
            provider_failure_detail=detail,
        )
        trace["attempts"] = [
            {
                "attempt_id": identity["attempt_id"],
                "status": "provider_failed",
                "failure_reason": reason,
                "failure_detail": detail,
            }
        ]
        return ""

    return _record_candidate_response(
        response,
        trace,
        identity,
        input_digest,
    )


def _record_candidate_response(
    response: Any,
    trace: dict[str, Any],
    identity: dict[str, str],
    input_digest: str,
) -> str:
    state = _candidate_response_state(response)
    trace.update(**_candidate_response_trace_fields(state))
    trace["attempts"] = [_candidate_attempt(state, identity, input_digest)]
    return str(state["typed_candidate"])


def _candidate_response_state(response: Any) -> dict[str, Any]:
    raw = response_text(response)
    bounded_raw = raw[:QASPER_CANDIDATE_MAX_RESPONSE_CHARS]
    cleaned = bounded_raw.strip()
    raw_candidate, raw_failure = parse_qasper_candidate(bounded_raw)
    candidate, failure = parse_qasper_candidate(cleaned)
    raw_candidate_identity_preserved = bool(
        raw_candidate and candidate and raw_candidate == candidate
    )
    finish_reason = response_finish_reason(response)
    provider_output_digest = _digest(raw)
    raw_response_digest = _digest(bounded_raw)
    state = {
        "raw_response": bounded_raw,
        "raw_response_digest": raw_response_digest,
        "provider_output_digest": provider_output_digest,
        "raw_response_truncated": len(raw) > QASPER_CANDIDATE_MAX_RESPONSE_CHARS,
        "cleaned_response": cleaned,
        "raw_candidate": raw_candidate,
        "raw_candidate_failure_reason": raw_failure,
        "raw_candidate_digest": _digest(raw_candidate),
        "typed_candidate": candidate,
        "typed_candidate_digest": _digest(candidate),
        "raw_candidate_identity_preserved": raw_candidate_identity_preserved,
        "status": "parsed" if candidate else "failed",
        "failure_reason": failure,
        "finish_reason": finish_reason,
        "completion_tokens": response_completion_tokens(response),
        "actual_input_tokens": _response_prompt_tokens(response),
    }
    state["actual_input_token_count"] = state["actual_input_tokens"]
    state["output_digest"] = _digest(
        {
            "raw_response_digest": raw_response_digest,
            "provider_output_digest": provider_output_digest,
            "cleaned_response_digest": _digest(cleaned),
            "raw_candidate": raw_candidate,
            "raw_candidate_digest": _digest(raw_candidate),
            "typed_candidate": candidate,
            "typed_candidate_digest": _digest(candidate),
            "raw_candidate_identity_preserved": raw_candidate_identity_preserved,
            "status": "parsed" if candidate else "failed",
            "failure_reason": failure,
            "finish_reason": finish_reason,
        }
    )
    return state


def _candidate_response_trace_fields(state: dict[str, Any]) -> dict[str, Any]:
    return {
        **state,
        "transformation_stages": [
            {
                "stage": "raw_response",
                "value": state["raw_response"],
                "digest": state["raw_response_digest"],
                "failure_reason": "",
            },
            {
                "stage": "cleaning",
                "value": state["cleaned_response"],
                "digest": _digest(state["cleaned_response"]),
                "changed": state["raw_response"] != state["cleaned_response"],
                "failure_reason": (
                    "" if state["cleaned_response"] else "empty_cleaned_response"
                ),
            },
            {
                "stage": "typed_candidate",
                "value": state["typed_candidate"],
                "digest": state["typed_candidate_digest"],
                "failure_reason": state["failure_reason"],
                "source_stage": "cleaning",
                "identity_preserved": state["raw_candidate_identity_preserved"],
            },
        ],
    }


def _candidate_attempt(
    state: dict[str, Any],
    identity: dict[str, str],
    input_digest: str,
) -> dict[str, Any]:
    keys = (
        "status",
        "failure_reason",
        "raw_response",
        "cleaned_response",
        "raw_candidate",
        "raw_candidate_digest",
        "typed_candidate",
        "typed_candidate_digest",
        "raw_candidate_identity_preserved",
        "finish_reason",
        "completion_tokens",
        "actual_input_tokens",
        "actual_input_token_count",
        "output_digest",
    )
    return {
        "attempt_id": identity["attempt_id"],
        **{key: state[key] for key in keys},
        "input_digest": input_digest,
    }


def qasper_candidate_response_format() -> dict[str, Any]:
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "qasper_typed_candidate",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "candidate": {
                        "type": "string",
                        "enum": sorted(QASPER_CANDIDATES),
                    }
                },
                "required": ["candidate"],
                "additionalProperties": False,
            },
        },
    }


def parse_qasper_candidate(text: str) -> tuple[str, str]:
    try:
        payload = json.loads(str(text or ""))
    except (TypeError, json.JSONDecodeError):
        return "", "json_decode_error"
    if not isinstance(payload, dict) or set(payload) != {"candidate"}:
        return "", "candidate_schema_invalid"
    candidate = str(payload.get("candidate") or "").strip().casefold()
    if candidate not in QASPER_CANDIDATES:
        return "", "candidate_enum_invalid"
    return candidate, ""


def _answering_llm(pipeline: Any) -> Any | None:
    answering_pipeline = getattr(pipeline, "answering_pipeline", None)
    llm = getattr(answering_pipeline, "llm", None)
    return llm if callable(llm) else None


def _response_prompt_tokens(response: Any | None) -> int:
    if response is None:
        return -1
    owners = (response, getattr(response, "raw", None))
    for owner in owners:
        for key in ("prompt_tokens", "input_tokens"):
            value = _response_usage_value(owner, key)
            if value >= 0:
                return value
    return -1


def _response_usage_value(response: Any | None, key: str) -> int:
    if response is None:
        return -1
    values = [getattr(response, key, None)]
    for container_name in (
        "usage",
        "usage_metadata",
        "response_metadata",
        "additional_kwargs",
    ):
        container = getattr(response, container_name, None)
        if isinstance(container, dict):
            values.extend(
                [
                    container.get(key),
                    container.get("token_usage", {}).get(key)
                    if isinstance(container.get("token_usage"), dict)
                    else None,
                ]
            )
        else:
            values.append(getattr(container, key, None))
    for value in values:
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return -1


def _serialized_messages(messages: list[Any]) -> list[dict[str, Any]]:
    return [
        {
            "index": index,
            "role": "system" if isinstance(message, SystemMessage) else "user",
            "content": deepcopy(message.content),
        }
        for index, message in enumerate(messages)
    ]
