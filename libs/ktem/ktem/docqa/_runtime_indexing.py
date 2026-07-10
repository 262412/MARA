from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Optional, cast

from ktem.index.file.archive import extract_supported_zip_files

from kotaemon.base import Document

from ._runtime_models import DocQAIndexResult
from ._runtime_utils import _serialize_value


def expand_index_inputs(
    file_index: Any,
    paths: list[str],
    *,
    zip_input_dir: str | Path,
) -> list[str]:
    if not file_index:
        return []

    supported_types = _supported_file_types(file_index)
    collected: list[str] = []
    for raw_path in paths:
        candidate = str(raw_path or "").strip()
        if not candidate:
            continue
        if _is_url(candidate):
            collected.append(candidate)
            continue

        path = Path(candidate).expanduser()
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {candidate}")
        if path.is_dir():
            collected.extend(_supported_children(path, supported_types))
            continue
        collected.append(str(path.resolve()))

    return expand_zip_inputs(
        file_index,
        collected,
        zip_input_dir=zip_input_dir,
    )


def expand_zip_inputs(
    file_index: Any,
    paths: list[str],
    *,
    zip_input_dir: str | Path,
) -> list[str]:
    if not file_index:
        return paths

    supported_types = _supported_file_types(file_index)
    expanded: list[str] = []
    for raw_path in paths:
        if _is_url(raw_path):
            expanded.append(raw_path)
            continue
        path = Path(raw_path)
        if path.suffix.lower() != ".zip":
            expanded.append(str(path))
            continue
        expanded.extend(
            _extract_supported_zip_children(path, supported_types, zip_input_dir)
        )
    return expanded


def index_paths(
    file_index: Any,
    paths: list[str],
    *,
    reindex: bool,
    settings: Optional[dict[str, Any]],
    load_settings: Any,
    resolve_user_id: Any,
    user_id: Any,
    zip_input_dir: str | Path,
) -> DocQAIndexResult:
    if not file_index:
        raise ValueError("No file index is configured.")

    resolved_user_id = resolve_user_id(user_id)
    runtime_settings = deepcopy(settings or load_settings(resolved_user_id))
    expanded_paths = expand_index_inputs(
        file_index,
        paths,
        zip_input_dir=zip_input_dir,
    )
    pipeline = file_index.get_indexing_pipeline(runtime_settings, resolved_user_id)
    return _consume_indexing_stream(pipeline, expanded_paths, reindex)


def _supported_file_types(file_index: Any) -> set[str]:
    return {
        item.strip().lower()
        for item in str(file_index.config.get("supported_file_types", "")).split(",")
        if item.strip()
    }


def _is_url(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def _supported_children(path: Path, supported_types: set[str]) -> list[str]:
    return [
        str(child.resolve())
        for child in sorted(path.rglob("*"))
        if child.is_file() and child.suffix.lower() in supported_types
    ]


def _extract_supported_zip_children(
    path: Path,
    supported_types: set[str],
    zip_input_dir: str | Path,
) -> list[str]:
    return extract_supported_zip_files(
        path,
        destination_parent=zip_input_dir,
        supported_types=supported_types,
    )


def _consume_indexing_stream(
    pipeline: Any,
    expanded_paths: list[str],
    reindex: bool,
) -> DocQAIndexResult:
    successes: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    debug_messages: list[str] = []
    index_inputs = cast(list[str | Path], expanded_paths)
    for response in pipeline.stream(index_inputs, reindex=reindex):
        _capture_indexing_response(response, successes, failures, debug_messages)
    return DocQAIndexResult(
        successes=successes,
        failures=failures,
        debug_messages=debug_messages,
    )


def _capture_indexing_response(
    response: Document,
    successes: list[dict[str, Any]],
    failures: list[dict[str, Any]],
    debug_messages: list[str],
) -> None:
    if response.channel == "debug":
        debug_messages.append(str(response.text))
    elif response.channel == "index":
        content = dict(response.content or {})
        serialized = {key: _serialize_value(value) for key, value in content.items()}
        if serialized.get("status") == "success":
            successes.append(serialized)
        else:
            failures.append(serialized)
