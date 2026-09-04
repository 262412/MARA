#!/usr/bin/env python3
"""Hard-check an OpenAI-compatible text service and its tool-call contract."""

from __future__ import annotations

import argparse
import json
import urllib.request
from pathlib import Path
from typing import Any


def _request_json(
    url: str,
    *,
    payload: dict[str, Any] | None = None,
    timeout_seconds: float,
) -> dict[str, Any]:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Authorization": "Bearer local", "Content-Type": "application/json"},
        method="POST" if data is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        return json.loads(response.read().decode())


def _chat(
    base_url: str,
    model: str,
    prompt: str,
    *,
    timeout_seconds: float,
    tool: dict[str, Any] | None = None,
    tool_choice: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 128,
        "temperature": 0,
    }
    if tool is not None:
        payload["tools"] = [{"type": "function", "function": tool}]
        payload["tool_choice"] = tool_choice
    return _request_json(
        f"{base_url.rstrip('/')}/chat/completions",
        payload=payload,
        timeout_seconds=timeout_seconds,
    )


def _message(response: dict[str, Any]) -> dict[str, Any]:
    choices = response.get("choices") or []
    if not choices or not isinstance(choices[0].get("message"), dict):
        raise ValueError("chat completion did not return a message")
    return choices[0]["message"]


def _require_tool_call(response: dict[str, Any], expected_name: str) -> dict[str, Any]:
    tool_calls = _message(response).get("tool_calls") or []
    if not tool_calls:
        raise ValueError(
            f"{expected_name} tool call was not emitted: "
            f"{json.dumps(response, sort_keys=True)}"
        )
    function = tool_calls[0].get("function") or {}
    if function.get("name") != expected_name:
        raise ValueError(
            f"expected {expected_name} tool call, got {function.get('name')}"
        )
    arguments = function.get("arguments")
    return (
        json.loads(arguments) if isinstance(arguments, str) else dict(arguments or {})
    )


def _record_result_tool() -> dict[str, Any]:
    return {
        "name": "RecordResult",
        "description": "Record the requested smoke-test value.",
        "parameters": {
            "type": "object",
            "properties": {"value": {"type": "string"}},
            "required": ["value"],
        },
    }


def _citation_tool() -> dict[str, Any]:
    return {
        "name": "CiteEvidence",
        "description": "List direct evidence quotes supporting the answer.",
        "parameters": {
            "type": "object",
            "properties": {
                "evidences": {
                    "type": "array",
                    "items": {"type": "string"},
                }
            },
            "required": ["evidences"],
        },
    }


def run_smoke(
    base_url: str,
    *,
    model: str | None = None,
    timeout_seconds: float = 60,
) -> dict[str, Any]:
    models = _request_json(
        f"{base_url.rstrip('/')}/models", timeout_seconds=timeout_seconds
    )
    selected_model = model or str((models.get("data") or [{}])[0].get("id") or "")
    if not selected_model:
        raise ValueError("model discovery returned no model id")

    text = _message(
        _chat(
            base_url,
            selected_model,
            "Reply with the word pong.",
            timeout_seconds=timeout_seconds,
        )
    ).get("content")
    if not str(text or "").strip():
        raise ValueError("text completion returned empty content")

    record_tool = _record_result_tool()
    for tool_choice in ("required", "auto"):
        response = _chat(
            base_url,
            selected_model,
            "Call RecordResult with value ok. Do not answer in plain text.",
            timeout_seconds=timeout_seconds,
            tool=record_tool,
            tool_choice=tool_choice,
        )
        _require_tool_call(response, "RecordResult")

    citation = _chat(
        base_url,
        selected_model,
        "Context: Alpha evidence. Cite the exact evidence for: What is available?",
        timeout_seconds=timeout_seconds,
        tool=_citation_tool(),
        tool_choice="required",
    )
    citation_arguments = _require_tool_call(citation, "CiteEvidence")
    if not citation_arguments.get("evidences"):
        raise ValueError("citation tool call returned no evidence")

    return {
        "status": "passed",
        "model": selected_model,
        "text_completion": True,
        "required_tool_call": True,
        "auto_tool_call": True,
        "citation_request": True,
        "citation_tool_call_error_count": 0,
        "inline_structured_citation_path_executed": True,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--model")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=60)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        result = run_smoke(
            args.base_url,
            model=args.model,
            timeout_seconds=args.timeout_seconds,
        )
    except (OSError, TypeError, ValueError) as exc:
        result = {
            "status": "failed",
            "citation_tool_call_error_count": 1,
            "inline_structured_citation_path_executed": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
        exit_code = 1
    else:
        exit_code = 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(f"citation_tool_call_error_count={result['citation_tool_call_error_count']}")
    print(
        "inline_structured_citation_path_executed="
        f"{str(result['inline_structured_citation_path_executed']).lower()}"
    )
    print(f"tool_call_smoke_status={result['status']}")
    print(f"tool_call_smoke_artifact={args.output}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
