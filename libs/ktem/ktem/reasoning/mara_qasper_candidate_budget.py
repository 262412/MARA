from __future__ import annotations

import json
from functools import lru_cache
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

from .mara_qasper_candidate_identity import candidate_digest as _digest

QASPER_CANDIDATE_MAX_MODEL_LEN = 4096
QASPER_CANDIDATE_MAX_TOKENS = 48
QASPER_CANDIDATE_TOKEN_HEADROOM = 128
QASPER_CANDIDATE_INPUT_TOKEN_BUDGET = (
    QASPER_CANDIDATE_MAX_MODEL_LEN
    - QASPER_CANDIDATE_MAX_TOKENS
    - QASPER_CANDIDATE_TOKEN_HEADROOM
)


def estimate_qasper_candidate_input_tokens(
    llm: Any | None,
    messages: list[Any],
    response_schema: dict[str, Any],
) -> int:
    return int(
        candidate_input_token_measurement(llm, messages, response_schema)[
            "estimated_input_tokens"
        ]
    )


def candidate_input_token_measurement(
    llm: Any | None,
    messages: list[Any],
    response_schema: dict[str, Any],
) -> dict[str, Any]:
    model = _model_name(llm)
    provider_measurement = _provider_measurement(llm, model, messages, response_schema)
    if provider_measurement is not None:
        return provider_measurement

    owners = _tokenizer_owners(llm)
    for identity, owner in owners:
        measurement = _tokenizer_measurement(owner, identity, messages, response_schema)
        if measurement is not None:
            return measurement

    measurement = _model_tokenizer_measurement(model, messages, response_schema)
    if measurement is not None:
        return measurement

    for identity, owner in owners:
        measurement = _message_method_measurement(
            owner, identity, messages, response_schema
        )
        if measurement is not None:
            return measurement
    return _text_estimate(messages, response_schema)


def _provider_measurement(
    llm: Any | None,
    model: str,
    messages: list[Any],
    response_schema: dict[str, Any],
) -> dict[str, Any] | None:
    endpoint = _provider_tokenize_endpoint(llm, model)
    if not endpoint:
        return None
    message_count, message_failure = _provider_tokenize(
        endpoint,
        {
            "model": model,
            "messages": _message_payload(messages),
            "add_generation_prompt": True,
        },
        llm,
    )
    if message_count is None:
        return _provider_failure_measurement(
            endpoint,
            model,
            method="/tokenize(messages)",
            reason=f"messages:{message_failure}",
        )
    schema_count, schema_failure = _provider_tokenize(
        endpoint,
        {"model": model, "prompt": _schema_text(response_schema)},
        llm,
    )
    if schema_count is None:
        return _provider_failure_measurement(
            endpoint,
            model,
            method="/tokenize(schema)",
            reason=f"schema:{schema_failure}",
        )
    return _measurement(
        message_count + schema_count,
        message_count,
        schema_count,
        identity=f"vllm:{urlsplit(endpoint).netloc}:{model}",
        method="/tokenize(messages)+/tokenize(schema)",
        exact=True,
        endpoint=endpoint,
    )


def _provider_failure_measurement(
    endpoint: str,
    model: str,
    *,
    method: str,
    reason: str,
) -> dict[str, Any]:
    measurement = _measurement(
        -1,
        -1,
        -1,
        identity=f"vllm:{urlsplit(endpoint).netloc}:{model}",
        method=method,
        exact=False,
        endpoint=endpoint,
    )
    measurement.update(
        estimated_input_tokens=-1,
        message_tokens=-1,
        schema_tokens=-1,
        tokenizer_failed=True,
        tokenizer_failure_reason=reason,
    )
    return measurement


def _provider_tokenize_endpoint(llm: Any | None, model: str) -> str:
    for name in (
        "tokenizer_endpoint",
        "tokenize_endpoint",
        "tokenizer_url",
        "tokenize_url",
    ):
        endpoint = str(_safe_attr(llm, name) or "").strip()
        if endpoint:
            return endpoint.rstrip("/")
    base_url = ""
    for name in ("base_url", "openai_api_base"):
        base_url = str(_safe_attr(llm, name) or "").strip()
        if base_url:
            break
    if not base_url:
        return ""
    lowered = base_url.casefold()
    if not (
        "vllm" in lowered
        or model.casefold().startswith("qwen")
        or any(host in lowered for host in ("localhost", "127.0.0.1", "0.0.0.0"))
    ):
        return ""
    parsed = urlsplit(base_url)
    path = parsed.path.rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3]
    return urlunsplit((parsed.scheme, parsed.netloc, f"{path}/tokenize", "", ""))


def _provider_tokenize(
    endpoint: str,
    payload: dict[str, Any],
    llm: Any | None,
) -> tuple[int | None, str]:
    request = Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        ),
        headers=_provider_headers(llm),
        method="POST",
    )
    try:
        with urlopen(request, timeout=2.0) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError) as exc:
        return None, type(exc).__name__
    if not isinstance(body, dict):
        return None, "response_not_object"
    nested = body.get("data")
    if isinstance(nested, dict):
        body = nested
    for key in ("count", "token_count"):
        value = _integer(body.get(key))
        if value is not None:
            return value, ""
    for key in ("tokens", "token_ids", "input_ids"):
        value = body.get(key)
        if isinstance(value, (list, tuple)):
            return len(value), ""
    return None, "token_count_missing"


def _provider_headers(llm: Any | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    api_key = _safe_attr(llm, "api_key") or _safe_attr(llm, "openai_api_key")
    getter = _safe_attr(api_key, "get_secret_value")
    if callable(getter):
        api_key = getter()
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


def _tokenizer_owners(llm: Any | None) -> list[tuple[str, Any]]:
    owners: list[tuple[str, Any]] = []
    seen: set[int] = set()
    for identity, owner in (
        ("llm", llm),
        ("llm.tokenizer", _safe_attr(llm, "tokenizer")),
        ("llm._tokenizer", _safe_attr(llm, "_tokenizer")),
        ("llm._obj", _safe_attr(llm, "_obj")),
    ):
        if owner is not None and id(owner) not in seen:
            owners.append((identity, owner))
            seen.add(id(owner))
    return owners


def _tokenizer_measurement(
    owner: Any,
    identity: str,
    messages: list[Any],
    response_schema: dict[str, Any],
) -> dict[str, Any] | None:
    tokenizer = _safe_attr(owner, "tokenizer") or owner
    apply_chat_template = _safe_attr(tokenizer, "apply_chat_template")
    encode = _safe_attr(tokenizer, "encode")
    if not callable(encode):
        return None
    try:
        if callable(apply_chat_template):
            message_tokens = _token_length(
                apply_chat_template(
                    _message_payload(messages),
                    tokenize=True,
                    add_generation_prompt=True,
                )
            )
            method = "apply_chat_template+encode"
        else:
            message_tokens = _token_length(
                encode(_canonical_message_text(messages), add_special_tokens=False)
            )
            method = "encode(canonical_messages)+encode"
        schema_tokens = _token_length(
            encode(_schema_text(response_schema), add_special_tokens=False)
        )
    except (AttributeError, TypeError, ValueError, NotImplementedError):
        return None
    return _measurement(
        message_tokens + schema_tokens,
        message_tokens,
        schema_tokens,
        identity=identity,
        method=method,
        exact=True,
    )


def _message_method_measurement(
    owner: Any,
    identity: str,
    messages: list[Any],
    response_schema: dict[str, Any],
) -> dict[str, Any] | None:
    message_counter = _safe_attr(owner, "get_num_tokens_from_messages")
    text_counter = _safe_attr(owner, "get_num_tokens")
    if not callable(message_counter) or not callable(text_counter):
        return None
    try:
        message_tokens = _integer(message_counter(messages))
        schema_tokens = _integer(text_counter(_schema_text(response_schema)))
    except (AttributeError, TypeError, ValueError, NotImplementedError):
        return None
    if message_tokens is None or schema_tokens is None:
        return None
    return _measurement(
        message_tokens + schema_tokens,
        message_tokens,
        schema_tokens,
        identity=identity,
        method="get_num_tokens_from_messages+get_num_tokens",
        exact=False,
    )


def _model_tokenizer_measurement(
    model: str,
    messages: list[Any],
    response_schema: dict[str, Any],
) -> dict[str, Any] | None:
    tokenizer = _load_model_tokenizer(model)
    if tokenizer is None:
        return None
    return _tokenizer_measurement(
        tokenizer,
        f"transformers:{model}",
        messages,
        response_schema,
    )


@lru_cache(maxsize=8)
def _load_model_tokenizer(model: str) -> Any | None:
    if not model:
        return None
    try:
        from transformers import AutoTokenizer

        return AutoTokenizer.from_pretrained(model, local_files_only=True)
    except (ImportError, OSError, ValueError, RuntimeError):
        return None


def _text_estimate(
    messages: list[Any], response_schema: dict[str, Any]
) -> dict[str, Any]:
    message_text = _canonical_message_text(messages)
    schema_text = _schema_text(response_schema)
    message_tokens = _conservative_text_tokens(message_text)
    schema_tokens = _conservative_text_tokens(schema_text)
    return _measurement(
        message_tokens + schema_tokens,
        message_tokens,
        schema_tokens,
        identity="fallback:conservative_utf8",
        method="utf8_bytes_and_lexical_upper_bound",
        exact=False,
    )


def _measurement(
    total: int,
    message_tokens: int,
    schema_tokens: int,
    *,
    identity: str,
    method: str,
    exact: bool,
    endpoint: str = "",
) -> dict[str, Any]:
    return {
        "estimated_input_tokens": max(0, int(total)),
        "message_tokens": max(0, int(message_tokens)),
        "schema_tokens": max(0, int(schema_tokens)),
        "tokenizer_identity": identity,
        "tokenizer_method": method,
        "tokenizer_exact": exact,
        "tokenizer_endpoint": endpoint,
        "tokenizer_failed": False,
        "tokenizer_failure_reason": "",
    }


def candidate_generation_trace(
    *,
    model: str,
    identity: dict[str, str],
    route: str,
    seed: int,
    serialized_messages: list[dict[str, Any]],
    input_digest: str,
    evidence: list[dict[str, Any]],
    evidence_diagnostics: dict[str, Any],
    controlled_candidate: str,
    response_schema_digest: str,
    token_measurement: dict[str, Any],
    request_dropped_count: int,
) -> dict[str, Any]:
    """Build the auditable candidate request and tokenizer trace."""

    return {
        "contract_id": "qasper_typed_candidate_generation.v2",
        **identity,
        "status": "started",
        "failure_reason": "",
        "model": model,
        "route": route,
        "internal_route": route,
        "benchmark_route_id": identity.get("benchmark_route_id", ""),
        "effective_seed": seed,
        "message_stack": serialized_messages,
        "message_stack_digest": _digest(serialized_messages),
        "message_stack_chars": sum(
            len(str(message.get("content") or "")) for message in serialized_messages
        ),
        "input_digest": input_digest,
        "response_schema_digest": response_schema_digest,
        "schema_digest": response_schema_digest,
        **_candidate_token_trace(token_measurement),
        "request_dropped_evidence_count": request_dropped_count,
        "evidence_count": len(evidence),
        "evidence_digest": _digest(evidence),
        "candidate_input_mode": (
            "controlled_contract_probe" if controlled_candidate else "generated"
        ),
        "candidate_transport_contract_id": "qasper_candidate_transport_identity.v1",
        "controlled_original_candidate": controlled_candidate,
        "requested_controlled_candidate": controlled_candidate,
        **evidence_diagnostics,
        "attempts": [],
        "raw_response": "",
        "raw_response_truncated": False,
        "cleaned_response": "",
        "raw_candidate": "",
        "provider_raw_candidate": "",
        "raw_candidate_failure_reason": "",
        "provider_failure_reason": "",
        "provider_failure_detail": "",
        "raw_candidate_digest": "",
        "typed_candidate": "",
        "typed_candidate_digest": "",
        "cleaned_candidate": "",
        "verifier_input_candidate": "",
        "verifier_input_candidate_digest": "",
        "raw_candidate_identity_preserved": False,
        "candidate_transport_identity_preserved": False,
        "candidate_transport_status": "not_started",
        "verifier_execution_status": "not_started",
        "auditor_execution_status": "not_started",
        "verifier_transport_status": "verifier_not_started",
        "auditor_transport_status": "auditor_not_started",
        "output_digest": "",
        "finish_reason": "",
        "completion_tokens": -1,
        "actual_input_tokens": -1,
        "actual_input_token_count": -1,
        "transformation_stages": [],
    }


def _candidate_token_trace(token_measurement: dict[str, Any]) -> dict[str, Any]:
    estimated = token_measurement["estimated_input_tokens"]
    message_tokens = token_measurement["message_tokens"]
    schema_tokens = token_measurement["schema_tokens"]
    tokenizer = token_measurement["tokenizer_identity"]
    return {
        "max_model_len": QASPER_CANDIDATE_MAX_MODEL_LEN,
        "max_output_tokens": QASPER_CANDIDATE_MAX_TOKENS,
        "token_headroom_tokens": QASPER_CANDIDATE_TOKEN_HEADROOM,
        "input_token_budget": QASPER_CANDIDATE_INPUT_TOKEN_BUDGET,
        "candidate_input_token_budget": QASPER_CANDIDATE_INPUT_TOKEN_BUDGET,
        "estimated_input_tokens": estimated,
        "estimated_input_token_count": estimated,
        "estimated_message_tokens": message_tokens,
        "message_token_count": message_tokens,
        "estimated_schema_tokens": schema_tokens,
        "schema_token_count": schema_tokens,
        "tokenizer_identity": tokenizer,
        "tokenizer": tokenizer,
        "tokenizer_method": token_measurement["tokenizer_method"],
        "tokenizer_exact": token_measurement["tokenizer_exact"],
        "tokenizer_endpoint": token_measurement.get("tokenizer_endpoint", ""),
        "tokenizer_failed": bool(token_measurement.get("tokenizer_failed")),
        "tokenizer_failure_reason": token_measurement.get(
            "tokenizer_failure_reason", ""
        ),
        "token_budget": QASPER_CANDIDATE_INPUT_TOKEN_BUDGET,
    }


def candidate_drop_index(evidence: list[dict[str, Any]]) -> int | None:
    """Drop the least aligned optional record first, deterministically."""

    candidates = [
        item for item in enumerate(evidence) if not item[1].get("required_slot_ids")
    ]
    if not candidates:
        return None

    def key(item: tuple[int, dict[str, Any]]) -> tuple[float, int, int]:
        index, record = item
        alignment = float(record.get("proposition_alignment_score") or 0.0)
        exact_selector = bool(record.get("selectors"))
        return alignment, 1 if exact_selector else 0, -index

    return min(candidates, key=key)[0]


def _message_payload(messages: list[Any]) -> list[dict[str, Any]]:
    payload: list[dict[str, Any]] = []
    for message in messages:
        converter = _safe_attr(message, "to_openai_format")
        if callable(converter):
            value = converter()
            if isinstance(value, dict):
                payload.append(value)
                continue
        role = str(_safe_attr(message, "type") or "user")
        role = {"human": "user", "ai": "assistant"}.get(role, role)
        payload.append({"role": role, "content": _safe_attr(message, "content")})
    return payload


def _canonical_message_text(messages: list[Any]) -> str:
    return json.dumps(
        _message_payload(messages),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _schema_text(response_schema: dict[str, Any]) -> str:
    return json.dumps(
        {"response_format": response_schema},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _conservative_text_tokens(text: str) -> int:
    byte_count = len(text.encode("utf-8"))
    lexical_count = len(text.split())
    return max((byte_count + 1) // 2, lexical_count * 2, 1 if text else 0)


def _token_length(value: Any) -> int:
    if hasattr(value, "shape") and len(value.shape) > 1:
        return int(value.shape[-1])
    return len(value)


def _integer(value: Any) -> int | None:
    try:
        integer = int(value)
    except (TypeError, ValueError):
        return None
    return integer if integer >= 0 else None


def _model_name(llm: Any | None) -> str:
    for key in ("model_name", "model", "model_id"):
        value = str(_safe_attr(llm, key) or "").strip()
        if value:
            return value
    return ""


def _safe_attr(value: Any, name: str) -> Any:
    if value is None:
        return None
    try:
        return getattr(value, name, None)
    except (AttributeError, TypeError, ValueError):
        return None
