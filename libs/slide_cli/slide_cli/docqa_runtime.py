from __future__ import annotations

import json
import subprocess
import sys
from json import JSONDecodeError
from pathlib import Path
from typing import Any

import click

from ktem.docqa import DocQARuntime
from ktem.runtime_bootstrap import bootstrap_runtime_settings


def create_docqa_runtime() -> DocQARuntime:
    bootstrap_runtime_settings()
    return DocQARuntime()


def parse_graph_context_file(graph_context_file: str) -> dict[str, Any]:
    if not graph_context_file:
        return {}

    with Path(graph_context_file).open(encoding="utf-8") as file_obj:
        payload = json.load(file_obj)

    if not isinstance(payload, dict):
        raise click.ClickException("--graph-context-file must contain a JSON object.")
    return payload


def _extract_json_payload(raw_output: str) -> dict[str, Any]:
    lines = [line for line in str(raw_output or "").splitlines() if line.strip()]
    decoder = json.JSONDecoder()
    errors: list[str] = []
    for index, line in enumerate(lines):
        stripped = line.lstrip()
        if not (stripped.startswith("{") or stripped.startswith("[")):
            continue
        payload = "\n".join(lines[index:])
        try:
            parsed, _offset = decoder.raw_decode(payload)
            if isinstance(parsed, dict):
                return parsed
            return {"payload": parsed}
        except JSONDecodeError as exc:
            errors.append(f"line {index + 1}: {exc}")
    raise RuntimeError(
        "Unable to parse JSON payload from acceptance output.\n"
        f"Errors: {errors}\n"
        f"Raw output:\n{raw_output}"
    )


def run_docqa_acceptance_matrix(
    *, keep_artifacts: bool = False, verbose: bool = False
) -> dict[str, Any]:
    command = [sys.executable, "-m", "ktem.docqa.acceptance"]
    if keep_artifacts:
        command.append("--keep-artifacts")
    if verbose:
        command.append("--verbose")

    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    try:
        payload = _extract_json_payload(completed.stdout)
    except RuntimeError:
        if completed.returncode != 0:
            raise RuntimeError(
                "DocQA acceptance matrix failed before emitting structured output.\n"
                f"STDOUT:\n{completed.stdout}\n"
                f"STDERR:\n{completed.stderr}"
            ) from None
        raise

    if completed.returncode != 0 or payload.get("status") != "pass":
        details = [str(payload.get("error") or "DocQA acceptance matrix failed.")]
        if payload.get("work_dir"):
            details.append(f"Artifacts: {payload['work_dir']}")
        if payload.get("partial_results"):
            details.append(
                f"Completed checks: {len(payload.get('partial_results', []))}"
            )
        stderr_tail = str(payload.get("captured_stderr_tail") or "").strip()
        if stderr_tail:
            details.append(f"Captured stderr tail:\n{stderr_tail}")
        elif completed.stderr.strip():
            details.append(f"STDERR:\n{completed.stderr.strip()}")
        raise RuntimeError("\n".join(details))

    return payload


__all__ = [
    "create_docqa_runtime",
    "parse_graph_context_file",
    "run_docqa_acceptance_matrix",
]
