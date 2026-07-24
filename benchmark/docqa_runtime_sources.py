from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from .schemas import BenchmarkDocument

SHORT_SOURCE_TEXT_MAX_CHARS = 4096
TEXT_FORMAT_TYPES = {"txt", "text", "md", "markdown", "json", "jsonl", "csv"}


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
    checker_ready: bool | None = None
    checker = getattr(runtime, "has_search_index", None)
    if callable(checker):
        try:
            checker_ready = bool(checker(file_id))
        except (AttributeError, RuntimeError, TypeError, ValueError):
            checker_ready = None
        if checker_ready is False:
            return False

    file_index = getattr(runtime, "file_index", None)
    if file_index is None:
        return True if checker_ready is None else checker_ready

    index_ready = _file_index_search_ready(file_index, file_id)
    if index_ready is None:
        return True if checker_ready is None else checker_ready
    return index_ready


def has_element_index(runtime: Any, file_id: str) -> bool:
    file_index = getattr(runtime, "file_index", None)
    if file_index is None:
        return False
    try:
        resources = getattr(file_index, "_resources")
        index_table = resources["Index"]
        rows = _index_relation_rows(index_table, file_id)
    except (AttributeError, ImportError, KeyError, RuntimeError, TypeError, ValueError):
        return False
    return any(
        str(getattr(row, "relation_type", "") or "") == "element_index" for row in rows
    )


def _file_index_search_ready(file_index: Any, file_id: str) -> bool | None:
    try:
        resources = getattr(file_index, "_resources")
        index_table = resources["Index"]
        rows = _index_relation_rows(index_table, file_id)
    except (AttributeError, ImportError, KeyError, RuntimeError, TypeError, ValueError):
        return None

    relation_types = {str(getattr(row, "relation_type", "") or "") for row in rows}
    if "document" not in relation_types:
        return False
    vector_store = getattr(file_index, "_vs", None) or resources.get("VectorStore")
    if vector_store and "vector" not in relation_types:
        return False
    return _page_scoped_pdf_text_chunks_ready(rows, resources.get("DocStore"))


def canonicalize_docqa_hits(
    retrieved_hits: list[dict[str, Any]],
    documents: list[BenchmarkDocument],
    selected_file_ids: list[str],
) -> list[dict[str, Any]]:
    aliases = _docqa_source_aliases(documents, selected_file_ids)
    return [_canonicalize_docqa_hit(hit, aliases) for hit in retrieved_hits]


def canonicalize_docqa_citations(
    citations: list[str],
    documents: list[BenchmarkDocument],
    selected_file_ids: list[str],
) -> list[str]:
    aliases = _docqa_source_aliases(documents, selected_file_ids)
    canonical: list[str] = []
    for citation in citations:
        ref = _canonical_source_ref(citation, aliases)
        if ref and ref not in canonical:
            canonical.append(ref)
    return canonical


def selected_source_fallback_hits(
    documents: list[BenchmarkDocument],
    selected_file_ids: list[str],
) -> list[dict[str, Any]]:
    if len(documents) != 1 or len(selected_file_ids) != 1:
        return []

    document = documents[0]
    text = _short_text_document_content(document)
    if not text:
        return []

    source_id = selected_file_ids[0]
    return [
        {
            "evidence_id": f"{document.document_id}#source",
            "document_id": source_id,
            "source_id": source_id,
            "source_name": Path(document.path).name,
            "modality": "text",
            "text": text,
            "source_backrefs": [f"{source_id}#source"],
        }
    ]


def selected_source_fallback_text(
    documents: list[BenchmarkDocument],
    selected_file_ids: list[str],
) -> str:
    hits = selected_source_fallback_hits(documents, selected_file_ids)
    return str(hits[0].get("text") or "") if hits else ""


def _index_relation_rows(index_table: Any, file_id: str) -> list[Any]:
    if isinstance(index_table, Sequence):
        return [
            row
            for row in index_table
            if str(getattr(row, "source_id", file_id) or file_id) == file_id
        ]

    from ktem.db.engine import engine
    from sqlmodel import Session, select

    with Session(engine) as session:
        return list(
            session.exec(
                select(index_table).where(index_table.source_id == file_id)
            ).all()
        )


def _page_scoped_pdf_text_chunks_ready(rows: list[Any], docstore: Any) -> bool:
    if docstore is None:
        return True

    doc_ids = [
        str(getattr(row, "target_id", "") or "")
        for row in rows
        if str(getattr(row, "relation_type", "") or "") == "document"
    ]
    doc_ids = [doc_id for doc_id in doc_ids if doc_id]
    if not doc_ids:
        return True

    try:
        docs = list(docstore.get(doc_ids))
    except (AttributeError, KeyError, RuntimeError, TypeError, ValueError):
        return True
    if not docs or not any(_doc_is_pdf(doc) for doc in docs):
        return True

    return all(_doc_has_page_metadata(doc) for doc in docs if _is_text_chunk(doc))


def _is_text_chunk(doc: Any) -> bool:
    metadata = _doc_metadata(doc)
    doc_type = str(_metadata_value(metadata, "type") or "").strip().lower()
    if doc_type in {"thumbnail", "page_image", "image"}:
        return False
    return bool(str(getattr(doc, "text", "") or getattr(doc, "content", "") or ""))


def _doc_has_page_metadata(doc: Any) -> bool:
    metadata = _doc_metadata(doc)
    return any(
        _metadata_value(metadata, key) not in (None, "")
        for key in ("page_label", "page", "page_number", "page_num")
    )


def _doc_is_pdf(doc: Any) -> bool:
    metadata = _doc_metadata(doc)
    for key in ("file_name", "source_name", "path", "file_type"):
        value = str(_metadata_value(metadata, key) or "").strip().lower()
        if value.endswith(".pdf") or value == "pdf":
            return True
    return False


def _doc_metadata(doc: Any) -> dict[str, Any]:
    metadata = getattr(doc, "metadata", None)
    return metadata if isinstance(metadata, dict) else {}


def _metadata_value(metadata: dict[str, Any], key: str) -> Any:
    if key in metadata:
        return metadata[key]
    nested = metadata.get("metadata")
    if isinstance(nested, dict):
        return nested.get(key)
    return None


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
    fallback_ref = f"{canonical_id}#page:{page}" if page else f"{canonical_id}#source"
    if not refs:
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


def _short_text_document_content(document: BenchmarkDocument) -> str:
    format_type = str(document.format_type or "").strip().lower()
    path = Path(document.path)
    if format_type and format_type not in TEXT_FORMAT_TYPES:
        return ""
    if not format_type and path.suffix.lower().lstrip(".") not in TEXT_FORMAT_TYPES:
        return ""
    try:
        if path.stat().st_size > SHORT_SOURCE_TEXT_MAX_CHARS * 4:
            return ""
        text = path.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        return ""
    if len(text) > SHORT_SOURCE_TEXT_MAX_CHARS:
        return ""
    return text
