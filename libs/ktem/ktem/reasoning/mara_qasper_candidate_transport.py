from __future__ import annotations

import json
from typing import Any

from .mara_qasper_candidate_identity import candidate_digest as _digest
from .mara_semantic_proposition_debug import (
    response_completion_tokens,
    response_finish_reason,
    response_text,
)

QASPER_CANDIDATE_RESPONSE_CONTRACT = "qasper_typed_candidate.v1"
QASPER_CANDIDATES = {"yes", "no", "unanswerable"}
QASPER_CANDIDATE_MAX_RESPONSE_CHARS = 16_000


def candidate_response_state(
    response: Any,
    *,
    controlled_candidate: str,
) -> dict[str, Any]:
    raw = response_text(response)
    bounded_raw = raw[:QASPER_CANDIDATE_MAX_RESPONSE_CHARS]
    cleaned = bounded_raw.strip()
    raw_candidate, raw_failure = parse_qasper_candidate(bounded_raw)
    candidate, parse_failure = parse_qasper_candidate(cleaned)
    raw_identity = bool(raw_candidate and raw_candidate == candidate)
    transport_identity = bool(
        raw_identity
        and (
            not controlled_candidate
            or controlled_candidate == raw_candidate == candidate
        )
    )
    transport_failed = bool(controlled_candidate and not transport_identity)
    status = "failed" if transport_failed or not candidate else "parsed"
    failure_reason = "candidate_transport_failed" if transport_failed else parse_failure
    verifier_candidate = candidate if transport_identity else ""
    values = {
        "raw": raw,
        "bounded_raw": bounded_raw,
        "cleaned": cleaned,
        "raw_candidate": raw_candidate,
        "raw_failure": raw_failure,
        "candidate": candidate,
        "controlled_candidate": controlled_candidate,
        "raw_identity": raw_identity,
        "transport_identity": transport_identity,
        "verifier_candidate": verifier_candidate,
        "status": status,
        "failure_reason": failure_reason,
    }
    state = _candidate_state_fields(response, values)
    state["output_digest"] = _candidate_output_digest(state)
    return state


def _candidate_state_fields(
    response: Any,
    values: dict[str, Any],
) -> dict[str, Any]:
    raw = values["raw"]
    bounded_raw = values["bounded_raw"]
    cleaned = values["cleaned"]
    raw_candidate = values["raw_candidate"]
    candidate = values["candidate"]
    verifier_candidate = values["verifier_candidate"]
    prompt_tokens = response_prompt_tokens(response)
    return {
        "raw_response": bounded_raw,
        "raw_response_digest": _digest(bounded_raw),
        "provider_output_digest": _digest(raw),
        "raw_response_truncated": len(raw) > QASPER_CANDIDATE_MAX_RESPONSE_CHARS,
        "cleaned_response": cleaned,
        "raw_candidate": raw_candidate,
        "provider_raw_candidate": raw_candidate,
        "raw_candidate_failure_reason": values["raw_failure"],
        "raw_candidate_digest": _digest(raw_candidate),
        "typed_candidate": candidate,
        "typed_candidate_digest": _digest(candidate),
        "raw_candidate_identity_preserved": values["raw_identity"],
        "requested_controlled_candidate": values["controlled_candidate"],
        "cleaned_candidate": candidate,
        "verifier_input_candidate": verifier_candidate,
        "verifier_input_candidate_digest": _digest(verifier_candidate),
        "candidate_transport_identity_preserved": values["transport_identity"],
        "candidate_transport_status": (
            "passed" if values["transport_identity"] else "failed"
        ),
        "verifier_execution_status": "ready" if verifier_candidate else "not_started",
        "auditor_execution_status": "not_started",
        "verifier_transport_status": (
            "verifier_ready" if verifier_candidate else "verifier_not_started"
        ),
        "auditor_transport_status": "auditor_not_started",
        "status": values["status"],
        "failure_reason": values["failure_reason"],
        "finish_reason": response_finish_reason(response),
        "completion_tokens": response_completion_tokens(response),
        "actual_input_tokens": prompt_tokens,
        "actual_input_token_count": prompt_tokens,
    }


def _candidate_output_digest(state: dict[str, Any]) -> str:
    return _digest(
        {
            "raw_response_digest": state["raw_response_digest"],
            "provider_output_digest": state["provider_output_digest"],
            "cleaned_response_digest": _digest(state["cleaned_response"]),
            "raw_candidate": state["raw_candidate"],
            "raw_candidate_digest": state["raw_candidate_digest"],
            "typed_candidate": state["typed_candidate"],
            "typed_candidate_digest": state["typed_candidate_digest"],
            "raw_candidate_identity_preserved": state[
                "raw_candidate_identity_preserved"
            ],
            "status": state["status"],
            "failure_reason": state["failure_reason"],
            "finish_reason": state["finish_reason"],
        }
    )


def candidate_response_trace_fields(state: dict[str, Any]) -> dict[str, Any]:
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


def candidate_attempt(
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
        "requested_controlled_candidate",
        "provider_raw_candidate",
        "cleaned_candidate",
        "verifier_input_candidate",
        "verifier_input_candidate_digest",
        "candidate_transport_identity_preserved",
        "candidate_transport_status",
        "verifier_execution_status",
        "auditor_execution_status",
        "verifier_transport_status",
        "auditor_transport_status",
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


def qasper_candidate_response_format(
    *,
    controlled_candidate: str = "",
) -> dict[str, Any]:
    controlled_candidate = str(controlled_candidate or "").strip().casefold()
    if controlled_candidate and controlled_candidate not in QASPER_CANDIDATES:
        raise ValueError("invalid controlled QASPER candidate response schema")
    candidates = (
        [controlled_candidate] if controlled_candidate else sorted(QASPER_CANDIDATES)
    )
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
                        "enum": candidates,
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


def response_prompt_tokens(response: Any | None) -> int:
    if response is None:
        return -1
    for owner in (response, getattr(response, "raw", None)):
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
        if not isinstance(value, (str, int, float)):
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return -1
