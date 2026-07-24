from __future__ import annotations

import mimetypes
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from kotaemon.base import Document

from .performance_cache import JsonDiskCache, content_hash, file_hash, stable_cache_key

PARSE_CACHE_PAYLOAD_VERSION = 3

_PATH_NAME_METADATA_KEYS = {"file_name", "filename"}
_PATH_VALUE_METADATA_KEYS = {"file_path", "source"}


@dataclass
class CachedLoadResult:
    documents: list[Document]
    stats: dict[str, int]
    cache_hit: bool
    cache_key: str | None = None


def load_data_with_parse_cache(
    loader: Any,
    file_path: str | os.PathLike[str],
    *,
    extra_info: dict | None = None,
    cache_dir: str | os.PathLike[str] | None = None,
    reader_policy: dict | None = None,
    **load_kwargs: Any,
) -> CachedLoadResult:
    """Load parser output through a file-hash cache, then apply runtime metadata."""

    if not cache_dir:
        loaded_documents = loader.load_data(
            Path(file_path), extra_info=extra_info, **load_kwargs
        )
        return CachedLoadResult(
            documents=list(loaded_documents),
            stats={"hits": 0, "misses": 0, "writes": 0},
            cache_hit=False,
        )

    cache = JsonDiskCache(cache_dir, "parse")
    key = build_parse_cache_key(loader, file_path, reader_policy=reader_policy)
    found, cached_payload = cache.get_with_status(key)
    if found:
        decoded = _decode_cache_payload(
            cached_payload,
            require_sidecar=_requires_artifact_sidecar(loader),
        )
        if decoded is not None:
            payload, artifact_sidecar = decoded
            documents = documents_from_cache_payload(payload)
            documents = _apply_path_metadata(documents, payload, Path(file_path))
            documents = _apply_extra_info(documents, extra_info)
            _write_cached_artifact(
                loader,
                Path(file_path),
                extra_info,
                documents,
                artifact_sidecar,
            )
            return CachedLoadResult(
                documents=documents,
                stats=cache.stats.to_dict(),
                cache_hit=True,
                cache_key=key,
            )

    loaded_documents = loader.load_data(Path(file_path), extra_info=None, **load_kwargs)
    artifact_sidecar = getattr(loaded_documents, "artifact_sidecar", None)
    parsed_documents = list(loaded_documents)
    cache.set(
        key,
        _cache_payload(
            parsed_documents,
            artifact_sidecar=artifact_sidecar,
            file_path=Path(file_path),
            runtime_metadata_keys=(),
        ),
    )
    documents = _apply_extra_info(parsed_documents, extra_info)
    _write_cached_artifact(
        loader,
        Path(file_path),
        extra_info,
        documents,
        cast(dict[str, Any] | None, artifact_sidecar),
    )
    return CachedLoadResult(
        documents=documents,
        stats=cache.stats.to_dict(),
        cache_hit=False,
        cache_key=key,
    )


def build_parse_cache_key(
    loader: Any,
    file_path: str | os.PathLike[str],
    *,
    reader_policy: dict | None = None,
) -> str:
    path = Path(file_path)
    payload = {
        "file_hash": file_hash(path),
        "parser": f"{loader.__class__.__module__}.{loader.__class__.__name__}",
        "parser_version": _parser_version(loader),
        "path_context": _path_parse_context(path),
        "reader_policy": _json_safe(
            {
                **_loader_policy(loader),
                **(reader_policy or {}),
            }
        ),
    }
    return stable_cache_key("parse", payload)


def documents_to_cache_payload(
    documents: list[Document],
    *,
    file_path: Path | None = None,
    runtime_metadata_keys: Iterable[str] = (),
) -> list[dict[str, Any]]:
    excluded = set(runtime_metadata_keys)
    payload = []
    for document in documents:
        metadata = dict(document.metadata or {})
        for key in excluded:
            metadata.pop(key, None)
        path_metadata = _pop_path_metadata(metadata, file_path)
        item = {
            "doc_id": document.doc_id,
            "text": str(getattr(document, "text", "") or ""),
            "content": _json_safe(getattr(document, "content", None)),
            "metadata": _json_safe(metadata),
        }
        if path_metadata:
            item["path_metadata"] = path_metadata
        payload.append(item)
    return payload


def documents_from_cache_payload(payload: list[dict[str, Any]]) -> list[Document]:
    documents = []
    for item in payload:
        content = item.get("content")
        text = str(item.get("text") or "")
        document = Document(
            content if content is not None else text,
            id_=item.get("doc_id"),
            metadata=dict(item.get("metadata") or {}),
        )
        document.text = text
        document.content = content if content is not None else text
        documents.append(document)
    return documents


def _apply_extra_info(
    documents: list[Document], extra_info: dict | None
) -> list[Document]:
    if not extra_info:
        return documents

    applied = []
    for document in documents:
        copied = _copy_document(document)
        metadata = dict(copied.metadata or {})
        metadata.update(extra_info)
        copied.metadata = metadata
        applied.append(copied)
    return applied


def _apply_path_metadata(
    documents: list[Document],
    payload: list[dict[str, Any]],
    file_path: Path,
) -> list[Document]:
    applied = []
    values = {
        "name": file_path.name,
        "path": str(file_path),
        "resolved_path": str(file_path.resolve()),
    }
    for document, item in zip(documents, payload):
        roles = item.get("path_metadata")
        if not isinstance(roles, dict):
            applied.append(document)
            continue
        copied = _copy_document(document)
        metadata = dict(copied.metadata or {})
        for key, role in roles.items():
            if isinstance(key, str) and isinstance(role, str) and role in values:
                metadata[key] = values[role]
        copied.metadata = metadata
        applied.append(copied)
    return applied


def _copy_document(document: Any) -> Document:
    if isinstance(document, Document):
        return Document(document)
    return Document(
        text=str(getattr(document, "text", "") or ""),
        id_=str(getattr(document, "doc_id", "") or ""),
        metadata=dict(getattr(document, "metadata", {}) or {}),
    )


def _write_cached_artifact(
    loader: Any,
    file_path: Path,
    extra_info: dict | None,
    documents: list[Document],
    artifact_sidecar: dict[str, Any] | None,
) -> None:
    writer = getattr(loader, "write_cached_artifact", None)
    if callable(writer) and artifact_sidecar is not None:
        writer(
            file_path,
            extra_info=extra_info,
            documents=documents,
            artifact_sidecar=artifact_sidecar,
        )


def _cache_payload(
    documents: list[Document],
    *,
    artifact_sidecar: object,
    file_path: Path,
    runtime_metadata_keys: Iterable[str],
) -> dict[str, Any]:
    return {
        "version": PARSE_CACHE_PAYLOAD_VERSION,
        "documents": documents_to_cache_payload(
            documents,
            file_path=file_path,
            runtime_metadata_keys=runtime_metadata_keys,
        ),
        "artifact_sidecar": _json_safe(artifact_sidecar),
    }


def _decode_cache_payload(
    cached_payload: object,
    *,
    require_sidecar: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None] | None:
    if isinstance(cached_payload, list) and not require_sidecar:
        return cast(list[dict[str, Any]], cached_payload), None
    if not isinstance(cached_payload, dict):
        return None
    documents = cached_payload.get("documents")
    sidecar = cached_payload.get("artifact_sidecar")
    if (
        cached_payload.get("version") != PARSE_CACHE_PAYLOAD_VERSION
        or not isinstance(documents, list)
        or (require_sidecar and not _valid_artifact_sidecar(sidecar))
    ):
        return None
    return (
        cast(list[dict[str, Any]], documents),
        cast(dict[str, Any] | None, sidecar),
    )


def _valid_artifact_sidecar(value: object) -> bool:
    return isinstance(value, dict) and isinstance(value.get("markdown"), str)


def _requires_artifact_sidecar(loader: Any) -> bool:
    return bool(getattr(loader, "artifact_cache_version", None))


def _parser_version(loader: Any) -> str:
    for attr in ("parser_version", "version", "__version__"):
        value = getattr(loader, attr, None)
        if value:
            return str(value)
    return loader.__class__.__name__


def _loader_policy(loader: Any) -> dict[str, Any]:
    policy_attrs = (
        "reader_mode",
        "pdf_mode",
        "vlm_endpoint",
        "max_figures_to_caption",
        "max_figure_to_caption",
        "model",
        "output_content_format",
        "processed_file_format",
        "use_ocr",
        "ocr_endpoint",
        "api",
        "server_url",
        "artifact_cache_version",
    )
    return {
        attr: getattr(loader, attr)
        for attr in policy_attrs
        if hasattr(loader, attr) and getattr(loader, attr) is not None
    }


def _path_parse_context(path: Path) -> dict[str, str | None]:
    content_type, _encoding = mimetypes.guess_type(str(path))
    return {
        "suffix": path.suffix.casefold(),
        "effective_mime": content_type.casefold() if content_type else None,
    }


def _pop_path_metadata(
    metadata: dict[str, Any],
    file_path: Path | None,
) -> dict[str, str]:
    if file_path is None:
        return {}
    roles: dict[str, str] = {}
    for key in _PATH_NAME_METADATA_KEYS:
        if _normalized_path_metadata(metadata.get(key)) == file_path.name:
            roles[key] = "name"
    path_value = str(file_path)
    resolved_value = str(file_path.resolve())
    for key in _PATH_VALUE_METADATA_KEYS:
        value = _normalized_path_metadata(metadata.get(key))
        if value == resolved_value:
            roles[key] = "resolved_path"
        elif value == path_value:
            roles[key] = "path"
    for key in roles:
        metadata.pop(key)
    return roles


def _normalized_path_metadata(value: Any) -> str | None:
    if isinstance(value, (str, bytes, os.PathLike)):
        return os.fsdecode(value)
    return None


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, os.PathLike):
        return os.fspath(value)
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    try:
        content_hash(value)
    except (TypeError, ValueError):
        return str(value)
    return value
