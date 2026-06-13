from __future__ import annotations

from pathlib import Path
from typing import Any

from .schemas import BenchmarkDocument


def document_paths(documents: list[BenchmarkDocument]) -> list[str]:
    paths: list[str] = []
    for document in documents:
        path = str(document.path)
        if path and path not in paths:
            paths.append(path)
    return paths


def unindexed_document_paths(
    documents: list[BenchmarkDocument],
    *,
    indexed_paths: set[str],
) -> list[str]:
    return [path for path in document_paths(documents) if path not in indexed_paths]


def has_search_index(runtime: Any, file_id: str) -> bool:
    checker = getattr(runtime, "has_search_index", None)
    if callable(checker):
        try:
            return bool(checker(file_id))
        except (AttributeError, RuntimeError, TypeError, ValueError):
            return True

    file_index = getattr(runtime, "file_index", None)
    if file_index is None:
        return True

    try:
        resources = getattr(file_index, "_resources")
        index_table = resources["Index"]
        rows = _index_relation_rows(index_table, file_id)
    except (AttributeError, ImportError, KeyError, RuntimeError, TypeError, ValueError):
        return True

    relation_types = {str(getattr(row, "relation_type", "") or "") for row in rows}
    if "document" not in relation_types:
        return False
    vector_store = getattr(file_index, "_vs", None) or resources.get("VectorStore")
    return not vector_store or "vector" in relation_types


def canonicalize_docqa_hits(
    retrieved_hits: list[dict[str, Any]],
    documents: list[BenchmarkDocument],
    selected_file_ids: list[str],
) -> list[dict[str, Any]]:
    aliases = _docqa_source_aliases(documents, selected_file_ids)
    return [_canonicalize_docqa_hit(hit, aliases) for hit in retrieved_hits]


def _index_relation_rows(index_table: Any, file_id: str) -> list[Any]:
    from ktem import db as ktem_db
    from sqlmodel import Session, select

    with Session(getattr(ktem_db, "engine")) as session:
        return list(
            session.exec(
                select(index_table).where(index_table.source_id == file_id)
            ).all()
        )


def _docqa_source_aliases(
    documents: list[BenchmarkDocument],
    selected_file_ids: list[str],
) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for document, file_id in zip(documents, selected_file_ids):
        _add_source_alias(aliases, file_id, document.document_id)
    for document in documents:
        path = Path(document.path)
        for alias in (
            document.document_id,
            str(path),
            str(path.resolve()),
            path.name,
            path.stem,
        ):
            _add_source_alias(aliases, alias, document.document_id)
    return aliases


def _add_source_alias(
    aliases: dict[str, str],
    alias: Any,
    document_id: str,
) -> None:
    key = _source_alias_key(alias)
    if key:
        aliases[key] = document_id


def _canonicalize_docqa_hit(
    hit: dict[str, Any],
    aliases: dict[str, str],
) -> dict[str, Any]:
    normalized = dict(hit)
    canonical_id = _hit_canonical_document_id(normalized, aliases)
    if not canonical_id:
        return normalized

    runtime_source_id = str(
        normalized.get("source_id") or normalized.get("document_id") or ""
    ).strip()
    if runtime_source_id and runtime_source_id != canonical_id:
        normalized["runtime_source_id"] = runtime_source_id
    normalized["source_id"] = canonical_id
    normalized["document_id"] = canonical_id
    normalized["source_backrefs"] = _canonical_source_backrefs(
        normalized,
        aliases,
        canonical_id,
    )
    return normalized


def _hit_canonical_document_id(
    hit: dict[str, Any],
    aliases: dict[str, str],
) -> str:
    for key in ("source_id", "document_id", "source_name"):
        value = str(hit.get(key) or "").strip()
        canonical_id = aliases.get(_source_alias_key(value))
        if canonical_id:
            return canonical_id
        if key == "source_name":
            canonical_id = aliases.get(_source_alias_key(Path(value).stem))
            if canonical_id:
                return canonical_id
    for ref in hit.get("source_backrefs") or []:
        source, _, _ = str(ref or "").strip().partition("#")
        canonical_id = aliases.get(_source_alias_key(source))
        if canonical_id:
            return canonical_id
    return ""


def _canonical_source_backrefs(
    hit: dict[str, Any],
    aliases: dict[str, str],
    canonical_id: str,
) -> list[str]:
    refs: list[str] = []
    for ref in hit.get("source_backrefs") or []:
        canonical_ref = _canonical_source_ref(ref, aliases)
        if canonical_ref and canonical_ref not in refs:
            refs.append(canonical_ref)
    page = str(hit.get("page_label") or "").strip()
    fallback_ref = f"{canonical_id}#page:{page}" if page else ""
    if fallback_ref and not refs:
        refs.append(fallback_ref)
    return refs


def _canonical_source_ref(ref: Any, aliases: dict[str, str]) -> str:
    text = str(ref or "").strip()
    if not text:
        return ""
    source, separator, suffix = text.partition("#")
    canonical_id = aliases.get(_source_alias_key(source))
    if not canonical_id:
        return text
    return f"{canonical_id}{separator}{suffix}" if separator else canonical_id


def _source_alias_key(value: Any) -> str:
    text = str(value or "").strip()
    return normalized_path(text) if text else ""


def normalized_path(path: str) -> str:
    try:
        return str(Path(path).resolve()).lower()
    except (OSError, RuntimeError, TypeError, ValueError):
        return str(path or "").strip().lower()
