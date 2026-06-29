from __future__ import annotations

import json
import socket
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter
from typing import Any


@dataclass(frozen=True)
class BackendProbeSpec:
    role: str
    url: str
    kind: str
    expected_model: str = ""
    expected_family: str = ""


DEFAULT_MULTIMODAL_BACKENDS = (
    BackendProbeSpec(
        role="text_llm",
        url="http://127.0.0.1:8000/v1/models",
        kind="openai_models",
    ),
    BackendProbeSpec(
        role="vlm",
        url="http://127.0.0.1:8001/v1/models",
        kind="openai_models",
        expected_model="Qwen/Qwen3-VL-8B-Instruct",
    ),
    BackendProbeSpec(
        role="retrieval",
        url="http://127.0.0.1:8002/health",
        kind="health_ok",
    ),
    BackendProbeSpec(
        role="colvision",
        url="http://127.0.0.1:8003/health",
        kind="health_ok",
        expected_family="colqwen",
    ),
)


def check_multimodal_backends(
    *,
    timeout_seconds: float = 3.0,
    checked_at: str | None = None,
) -> dict[str, Any]:
    backends = {
        spec.role: _probe_backend(spec, timeout_seconds=timeout_seconds)
        for spec in DEFAULT_MULTIMODAL_BACKENDS
    }
    result = {
        "schema_version": 1,
        "checked_at": checked_at or datetime.now(timezone.utc).isoformat(),
        "overall_status": "ready",
        "backends": backends,
        "failure_taxonomy": [],
    }
    result["failure_taxonomy"] = summarize_backend_failures(result)
    if result["failure_taxonomy"]:
        result["overall_status"] = "blocked"
    return result


def summarize_backend_failures(health: dict[str, Any]) -> list[dict[str, str]]:
    rows = []
    backends = health.get("backends") or {}
    for role, item in backends.items():
        if not isinstance(item, dict) or item.get("status") == "ready":
            continue
        rows.append(
            {
                "role": str(item.get("role") or role),
                "failure_type": str(item.get("failure_type") or "unknown"),
                "status": str(item.get("status") or "blocked"),
            }
        )
    return rows


def _probe_backend(
    spec: BackendProbeSpec,
    *,
    timeout_seconds: float,
) -> dict[str, Any]:
    started_at = perf_counter()
    base = {"role": spec.role, "url": spec.url, "status": "blocked"}
    try:
        payload = _read_json(spec.url, timeout_seconds=timeout_seconds)
    except urllib.error.HTTPError as exc:
        return _blocked(base, "http_error", started_at, status_code=exc.code)
    except (TimeoutError, socket.timeout):
        return _blocked(base, "timeout", started_at)
    except urllib.error.URLError as exc:
        return _blocked(base, _url_error_type(exc), started_at, error=str(exc.reason))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        return _blocked(base, "bad_json", started_at, error=str(exc))

    return _classify_payload(spec, base, payload, started_at)


def _read_json(url: str, *, timeout_seconds: float) -> dict[str, Any]:
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode("utf-8"))


def _classify_payload(
    spec: BackendProbeSpec,
    base: dict[str, Any],
    payload: dict[str, Any],
    started_at: float,
) -> dict[str, Any]:
    if spec.kind == "openai_models":
        return _classify_models_payload(spec, base, payload, started_at)
    if payload.get("ok") is not True:
        return _blocked(base, "health_not_ok", started_at, error=payload.get("error"))
    if spec.expected_family:
        family = str(payload.get("model_family") or "").strip()
        if family and family != spec.expected_family:
            return _blocked(
                {**base, "model_family": family},
                "family_mismatch",
                started_at,
            )
    return _ready(base, started_at, payload)


def _classify_models_payload(
    spec: BackendProbeSpec,
    base: dict[str, Any],
    payload: dict[str, Any],
    started_at: float,
) -> dict[str, Any]:
    data = payload.get("data")
    if not isinstance(data, list):
        return _blocked(base, "unexpected_payload", started_at)
    models = [str(item.get("id") or "") for item in data if isinstance(item, dict)]
    models = [model for model in models if model]
    if spec.expected_model and spec.expected_model not in models:
        return _blocked({**base, "models": models}, "model_missing", started_at)
    return _ready({**base, "models": models}, started_at, payload)


def _ready(
    base: dict[str, Any],
    started_at: float,
    payload: dict[str, Any],
) -> dict[str, Any]:
    row = {
        **base,
        "status": "ready",
        "latency_seconds": _latency_seconds(started_at),
    }
    if payload.get("model_family"):
        row["model_family"] = payload.get("model_family")
    if payload.get("model"):
        row["model"] = payload.get("model")
    return row


def _blocked(
    base: dict[str, Any],
    failure_type: str,
    started_at: float,
    **extra: Any,
) -> dict[str, Any]:
    return {
        **base,
        "failure_type": failure_type,
        "latency_seconds": _latency_seconds(started_at),
        **{key: value for key, value in extra.items() if value not in (None, "")},
    }


def _url_error_type(exc: urllib.error.URLError) -> str:
    if isinstance(exc.reason, TimeoutError):
        return "timeout"
    if isinstance(exc.reason, ConnectionRefusedError):
        return "unreachable"
    return "unreachable"


def _latency_seconds(started_at: float) -> float:
    return round(perf_counter() - started_at, 4)
