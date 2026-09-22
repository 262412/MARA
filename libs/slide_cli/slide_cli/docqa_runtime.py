from __future__ import annotations

import json
import os
import subprocess
import sys
import warnings
from json import JSONDecodeError
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
from slide_cli.runtime_assets import (
    ensure_llama_index_nltk_cache,
    ensure_tiktoken_cache,
)

from . import docqa_inspection as _inspection
from .docqa_inspection import (
    collect_docqa_doctor_payload,
    collect_docqa_file_records,
    collect_docqa_session_summaries,
)

if TYPE_CHECKING:
    from ktem.docqa import DocQARuntime

# Preserve the original import surface for inspection consumers.
_serialize_value = _inspection._serialize_value
_extract_graph_source_ids = _inspection._extract_graph_source_ids
_load_json_dict = _inspection._load_json_dict
_resolve_default_user_id = _inspection._resolve_default_user_id
_pick_default_model_name = _inspection._pick_default_model_name
_pick_persisted_default_model_name = _inspection._pick_persisted_default_model_name
_warn_placeholder_credentials = _inspection._warn_placeholder_credentials
_resolve_file_index_definition = _inspection._resolve_file_index_definition
_count_indexed_files = _inspection._count_indexed_files
_count_saved_sessions = _inspection._count_saved_sessions


def create_docqa_runtime(
    *,
    include_query_features: bool = True,
    include_file_artifacts: bool | None = None,
    reasoning_paths: tuple[str, ...] | None = None,
) -> "DocQARuntime":
    ensure_llama_index_nltk_cache()
    ensure_tiktoken_cache()
    os.environ.setdefault("GRPC_VERBOSITY", "ERROR")
    os.environ.setdefault("GLOG_minloglevel", "3")
    os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

    try:
        from cryptography.utils import CryptographyDeprecationWarning
    except Exception:
        CryptographyDeprecationWarning = Warning

    warnings.filterwarnings(
        "ignore",
        message=r"ARC4 has been moved.*",
        category=CryptographyDeprecationWarning,
    )
    from ktem.runtime_bootstrap import bootstrap_runtime_settings

    bootstrap_runtime_settings()
    from .docqa_runtime_profile import configure_docqa_runtime_profile

    configure_docqa_runtime_profile(
        include_query_features=include_query_features,
        include_file_artifacts=include_file_artifacts,
        reasoning_paths=reasoning_paths,
    )
    from ktem.docqa import DocQARuntime

    return DocQARuntime()


def collect_docqa_import_capabilities() -> dict[str, list[str]]:
    from .docqa_import_capabilities import (
        collect_docqa_import_capabilities as _collect_docqa_import_capabilities,
    )

    return _collect_docqa_import_capabilities()


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
    "collect_docqa_doctor_payload",
    "collect_docqa_file_records",
    "collect_docqa_session_summaries",
    "create_docqa_runtime",
    "ensure_llama_index_nltk_cache",
    "parse_graph_context_file",
    "run_docqa_acceptance_matrix",
]
