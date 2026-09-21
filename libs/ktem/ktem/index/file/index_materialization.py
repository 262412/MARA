"""Turn borrowed parser/cache documents into Source-owned persistent chunks.

Only new writes use these IDs. Existing stored IDs and the parser cache format
remain readable unchanged; no historical collision is inferred or repaired.
"""

from __future__ import annotations

import json
import logging
from copy import deepcopy
from hashlib import sha256
from typing import Callable

from kotaemon.base import Document

logger = logging.getLogger(__name__)


def persistent_chunk_id(namespace: str, file_id: str, logical_id: str) -> str:
    payload = json.dumps(
        [namespace, file_id, logical_id], ensure_ascii=False, separators=(",", ":")
    )
    return "index-chunk:v1:" + sha256(payload.encode("utf-8")).hexdigest()


def materialize_index_chunks(
    documents: list[Document],
    *,
    namespace: str,
    file_id: str,
    file_name: str,
    splitter: Callable | None,
    deterministic_chunk_ids: bool,
    prepare_chunks: Callable,
) -> list[Document]:
    """Keep old split/order rules, but own every object before assigning IDs."""
    text_docs, non_text_docs, thumbnails = [], [], []
    for document in deepcopy(documents):
        document.metadata["file_id"] = file_id
        kind = document.metadata.get("type", "text")
        if kind == "text":
            text_docs.append(document)
        elif kind == "thumbnail":
            thumbnails.append(document)
        else:
            non_text_docs.append(document)
    text_chunks = splitter(text_docs) if splitter else text_docs
    original_ids = {
        id(chunk): chunk.doc_id for chunk in [*text_chunks, *non_text_docs, *thumbnails]
    }
    logger.debug("Got %d page thumbnails", len(thumbnails))
    chunks = prepare_chunks(
        text_chunks,
        non_text_docs,
        thumbnails,
        file_name=file_name,
        deterministic_chunk_ids=deterministic_chunk_ids,
    )
    identities = {
        chunk.doc_id: persistent_chunk_id(namespace, file_id, chunk.doc_id)
        for chunk in chunks
    }
    # Splitter relationships still name pre-stabilization chunks. Keep aliases
    # solely for reference remapping, never for deduplication or ranking.
    references = dict(identities)
    references.update(
        (original_ids[id(chunk)], identities[chunk.doc_id])
        for chunk in chunks
        if id(chunk) in original_ids
    )
    for chunk in chunks:
        chunk.doc_id = identities[chunk.doc_id]
        for key in ("thumbnail_doc_id", "page_thumbnail_doc_id"):
            reference = chunk.metadata.get(key)
            if reference in references:
                chunk.metadata[key] = references[reference]
        if chunk.source in references:
            chunk.source = references[chunk.source]
        for relation in chunk.relationships.values():
            related_nodes = relation if isinstance(relation, list) else [relation]
            for node in related_nodes:
                node.node_id = references.get(node.node_id) or persistent_chunk_id(
                    namespace, file_id, node.node_id
                )
    return chunks
