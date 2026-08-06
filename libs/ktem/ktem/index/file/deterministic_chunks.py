from __future__ import annotations

import json
from collections import defaultdict
from hashlib import sha256

from kotaemon.base import Document


def stabilize_chunk_identities(
    chunks: list[Document],
    *,
    source_identity: str,
) -> list[Document]:
    """Assign stable content/provenance IDs and ordering to fresh index chunks."""

    keyed = [(_stable_chunk_key(chunk, source_identity), chunk) for chunk in chunks]
    keyed.sort(key=lambda row: row[0])
    duplicate_counts: dict[tuple[str, ...], int] = defaultdict(int)
    stable_chunks: list[Document] = []
    for key, chunk in keyed:
        duplicate_ordinal = duplicate_counts[key]
        duplicate_counts[key] += 1
        identity_payload = json.dumps(
            [*key, str(duplicate_ordinal)],
            ensure_ascii=False,
            separators=(",", ":"),
        )
        chunk.doc_id = f"stable-chunk:{sha256(identity_payload.encode()).hexdigest()}"
        stable_chunks.append(chunk)
    return stable_chunks


def prepare_chunks_for_indexing(
    text_chunks: list[Document],
    non_text_docs: list[Document],
    thumbnail_docs: list[Document],
    *,
    file_name: str,
    deterministic_chunk_ids: bool,
) -> list[Document]:
    chunks = [*text_chunks, *non_text_docs, *thumbnail_docs]
    if deterministic_chunk_ids:
        chunks = stabilize_chunk_identities(chunks, source_identity=file_name)
    thumbnail_objects = {id(thumbnail) for thumbnail in thumbnail_docs}
    page_thumbnails = {
        chunk.metadata["page_label"]: chunk.doc_id
        for chunk in chunks
        if id(chunk) in thumbnail_objects
    }
    for chunk in text_chunks:
        page_label = chunk.metadata.get("page_label")
        if page_label in page_thumbnails:
            chunk.metadata["thumbnail_doc_id"] = page_thumbnails[page_label]
    return chunks


def _stable_chunk_key(chunk: Document, source_identity: str) -> tuple[str, ...]:
    metadata = dict(chunk.metadata or {})
    normalized_text = " ".join(str(chunk.text or "").casefold().split())
    stable_provenance = {
        key: metadata.get(key)
        for key in (
            "file_name",
            "page_label",
            "page_number",
            "section",
            "section_title",
            "element_type",
            "type",
        )
        if metadata.get(key) not in (None, "")
    }
    return (
        " ".join(str(source_identity or "").casefold().split()),
        json.dumps(
            stable_provenance,
            sort_keys=True,
            ensure_ascii=False,
            default=str,
            separators=(",", ":"),
        ),
        str(chunk.start_char_idx if chunk.start_char_idx is not None else ""),
        str(chunk.end_char_idx if chunk.end_char_idx is not None else ""),
        sha256(normalized_text.encode()).hexdigest(),
    )
