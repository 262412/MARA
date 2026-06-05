from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from typing import Any, Iterable

from kotaemon.base import Document

GRAPH_BUILDER = "local_graph_builder_v1"
GRAPH_INDEX_DOC_TYPE = "mara_graph_index"
GRAPH_INDEX_RELATION_TYPE = "graph_index"
GRAPH_INDEX_SCHEMA_VERSION = "1.0"


def local_graph_index_from_documents(
    documents: Iterable[Any],
    *,
    entity_extractor: Any = None,
    relation_extractor: Any = None,
    community_detector: Any = None,
    community_summarizer: Any = None,
) -> dict[str, Any]:
    docs = list(documents)
    entities, relations, claims = _local_graph_rows(docs)
    entity_rows = _backend_entities(docs, entity_extractor, entities)
    relation_rows = _backend_relations(
        docs,
        relation_extractor,
        entity_rows,
        relations,
    )
    community_rows = _backend_community_summaries(
        entity_rows,
        relation_rows,
        community_detector,
        community_summarizer,
    )
    metadata = {"graph_builder": GRAPH_BUILDER}
    metadata.update(
        _backend_metadata(
            entity_extractor,
            relation_extractor,
            community_detector,
            community_summarizer,
        )
    )
    return {
        "entities": entity_rows,
        "relations": relation_rows,
        "claims": claims,
        "community_summaries": community_rows,
        "metadata": metadata,
    }


def update_graph_index_incrementally(
    existing_graph_index: dict[str, Any],
    documents: Iterable[Any],
    *,
    entity_extractor: Any = None,
    relation_extractor: Any = None,
    community_detector: Any = None,
    community_summarizer: Any = None,
) -> dict[str, Any]:
    existing = existing_graph_index if isinstance(existing_graph_index, dict) else {}
    new_index = local_graph_index_from_documents(
        documents,
        entity_extractor=entity_extractor,
        relation_extractor=relation_extractor,
        community_detector=community_detector,
        community_summarizer=community_summarizer,
    )
    merged = _merge_graph_indexes([existing, new_index])
    entities = list(merged.get("entities") or [])
    relations = list(merged.get("relations") or [])
    merged["community_summaries"] = _backend_community_summaries(
        entities,
        relations,
        community_detector,
        community_summarizer,
    )
    merged["metadata"] = {
        "graph_builder": "incremental_graph_index_v1",
        "previous_entity_count": len(existing.get("entities") or []),
        "new_entity_count": len(new_index.get("entities") or []),
        "new_relation_count": len(new_index.get("relations") or []),
    }
    return merged


def _local_graph_rows(
    documents: list[Any],
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    entities: dict[str, dict[str, Any]] = {}
    relations: list[dict[str, Any]] = []
    claims: list[dict[str, Any]] = []

    for doc in documents:
        metadata = _metadata(doc)
        source_backrefs = _source_backrefs(metadata)
        text = _text(doc, metadata)
        for sentence in _sentences(text):
            relation = _relation_from_sentence(sentence, source_backrefs)
            if relation:
                relations.append(relation)
                _upsert_entity(entities, relation["source"], sentence, source_backrefs)
                _upsert_entity(entities, relation["target"], sentence, source_backrefs)
            for entity in _entities(sentence):
                _upsert_entity(entities, entity, sentence, source_backrefs)
            claims.append(_claim(sentence, source_backrefs))
    return entities, relations, claims


def _backend_entities(
    documents: list[Any],
    entity_extractor: Any,
    local_entities: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    if entity_extractor is None:
        return list(local_entities.values())
    return _dict_rows(entity_extractor.extract(documents))


def _backend_relations(
    documents: list[Any],
    relation_extractor: Any,
    entities: list[dict[str, Any]],
    local_relations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if relation_extractor is None:
        return local_relations
    return _dict_rows(relation_extractor.extract(documents, entities))


def _backend_community_summaries(
    entities: list[dict[str, Any]],
    relations: list[dict[str, Any]],
    community_detector: Any,
    community_summarizer: Any,
) -> list[dict[str, Any]]:
    if community_detector is None and community_summarizer is None:
        return _community_summaries(entities, relations)
    descriptors = (
        _dict_rows(community_detector.detect(entities, relations))
        if community_detector is not None
        else _community_descriptors(entities, relations)
    )
    return [
        _community_summary_from_descriptor(
            descriptor,
            entities,
            relations,
            community_summarizer,
        )
        for descriptor in descriptors
    ]


def _community_summary_from_descriptor(
    descriptor: dict[str, Any],
    entities: list[dict[str, Any]],
    relations: list[dict[str, Any]],
    community_summarizer: Any,
) -> dict[str, Any]:
    entity_rows = _community_entities(descriptor, entities)
    relation_rows = _community_relations(descriptor, relations)
    if community_summarizer is not None:
        return dict(
            community_summarizer.summarize(descriptor, entity_rows, relation_rows)
        )
    local = _community_summaries(entity_rows, relation_rows)
    if local:
        row = dict(local[0])
        row["id"] = str(descriptor.get("id") or row.get("id") or "")
        return row
    return {
        "id": str(descriptor.get("id") or "community"),
        "label": "",
        "summary": "",
        "entity_ids": list(descriptor.get("entity_ids") or []),
        "source_backrefs": [],
    }


def _community_descriptors(
    entities: list[dict[str, Any]],
    relations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "id": item["id"],
            "entity_ids": list(item.get("entity_ids") or []),
            "relation_ids": _relation_ids_for_entities(
                relations,
                list(item.get("entity_ids") or []),
            ),
        }
        for item in _community_summaries(entities, relations)
    ]


def _community_entities(
    descriptor: dict[str, Any],
    entities: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    entity_ids = {str(item) for item in descriptor.get("entity_ids") or []}
    return [item for item in entities if str(item.get("id") or "") in entity_ids]


def _community_relations(
    descriptor: dict[str, Any],
    relations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    relation_ids = {str(item) for item in descriptor.get("relation_ids") or []}
    if relation_ids:
        return [item for item in relations if str(item.get("id") or "") in relation_ids]
    entity_ids = {str(item) for item in descriptor.get("entity_ids") or []}
    return [
        item
        for item in relations
        if _slug(str(item.get("source") or "")) in entity_ids
        or _slug(str(item.get("target") or "")) in entity_ids
    ]


def _relation_ids_for_entities(
    relations: list[dict[str, Any]],
    entity_ids: list[str],
) -> list[str]:
    entity_set = set(entity_ids)
    return [
        str(item.get("id") or "")
        for item in relations
        if _slug(str(item.get("source") or "")) in entity_set
        or _slug(str(item.get("target") or "")) in entity_set
    ]


def _dict_rows(rows: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in rows or [] if isinstance(item, dict)]


def _backend_metadata(*backends: Any) -> dict[str, str]:
    keys = (
        "entity_extraction_backend",
        "relation_extraction_backend",
        "community_detection_backend",
        "community_summary_backend",
    )
    return {
        key: _backend_name(backend)
        for key, backend in zip(keys, backends)
        if backend is not None
    }


def _backend_name(backend: Any) -> str:
    return str(getattr(backend, "name", None) or backend.__class__.__name__)


def graph_index_documents_from_documents(
    file_id: str,
    documents: Iterable[Any],
) -> list[Document]:
    source_id = str(file_id or "").strip()
    graph_index = local_graph_index_from_documents(documents)
    if not graph_index.get("entities") and not graph_index.get("relations"):
        return []
    metadata = {
        "type": GRAPH_INDEX_DOC_TYPE,
        "source_id": source_id,
        "file_id": source_id,
        "graph_index_relation_type": GRAPH_INDEX_RELATION_TYPE,
        "graph_index_schema_version": GRAPH_INDEX_SCHEMA_VERSION,
        "graph_index": graph_index,
    }
    return [
        Document(
            text=_graph_index_text(graph_index),
            id_=_graph_index_doc_id(source_id, graph_index),
            metadata=metadata,
        )
    ]


def graph_index_from_index_documents(documents: Iterable[Any]) -> dict[str, Any]:
    graph_indexes = []
    for doc in documents:
        metadata = _metadata(doc)
        if metadata.get("type") != GRAPH_INDEX_DOC_TYPE:
            continue
        graph_index = metadata.get("graph_index")
        if isinstance(graph_index, dict):
            graph_indexes.append(graph_index)
    if not graph_indexes:
        return {}
    if len(graph_indexes) == 1:
        return dict(graph_indexes[0])
    return _merge_graph_indexes(graph_indexes)


def _merge_graph_indexes(graph_indexes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "entities": _dedupe_graph_rows(graph_indexes, "entities"),
        "relations": _dedupe_graph_rows(graph_indexes, "relations"),
        "claims": _dedupe_graph_rows(graph_indexes, "claims"),
        "community_summaries": _dedupe_graph_rows(
            graph_indexes,
            "community_summaries",
        ),
        "metadata": {
            "graph_builder": "merged_persisted_graph_index_v1",
            "source_index_count": len(graph_indexes),
        },
    }


def _dedupe_graph_rows(
    graph_indexes: list[dict[str, Any]],
    key: str,
) -> list[dict[str, Any]]:
    rows = []
    seen: set[str] = set()
    for graph_index in graph_indexes:
        for item in graph_index.get(key) or []:
            if not isinstance(item, dict):
                continue
            row_id = str(item.get("id") or item.get("text") or item).strip()
            if row_id in seen:
                continue
            seen.add(row_id)
            rows.append(dict(item))
    return rows


def _graph_index_text(graph_index: dict[str, Any]) -> str:
    return "\n".join(
        str(item.get("summary") or item.get("description") or item.get("text") or "")
        for section in ("community_summaries", "relations", "claims", "entities")
        for item in graph_index.get(section) or []
        if isinstance(item, dict)
    ).strip()


def _graph_index_doc_id(file_id: str, graph_index: dict[str, Any]) -> str:
    payload = json.dumps(graph_index, sort_keys=True, default=str)
    digest = hashlib.sha256(f"{file_id}\n{payload}".encode("utf-8")).hexdigest()
    return f"graph-index:{file_id}:{digest[:16]}"


def _relation_from_sentence(
    sentence: str,
    source_backrefs: list[str],
) -> dict[str, Any] | None:
    pattern = re.compile(
        r"\b([A-Z][A-Za-z0-9 _-]{1,60}?)\s+"
        r"(supports|connects|relates to|drives|influences|depends on)\s+"
        r"([A-Z][A-Za-z0-9 _-]{1,60}?)(?:\.|$)"
    )
    match = pattern.search(sentence)
    if not match:
        return None
    source = _clean_entity(match.group(1))
    target = _clean_entity(match.group(3))
    relation = match.group(2)
    return {
        "id": f"{_slug(source)}-{relation.replace(' ', '-')}-{_slug(target)}",
        "source": source,
        "target": target,
        "label": relation,
        "description": sentence,
        "source_backrefs": source_backrefs,
    }


def _upsert_entity(
    entities: dict[str, dict[str, Any]],
    label: str,
    sentence: str,
    source_backrefs: list[str],
) -> None:
    if not label:
        return
    key = _slug(label)
    if key not in entities:
        entities[key] = {
            "id": key,
            "label": label,
            "summary": sentence,
            "source_backrefs": list(source_backrefs),
        }
        return
    existing = entities[key]
    for ref in source_backrefs:
        if ref not in existing["source_backrefs"]:
            existing["source_backrefs"].append(ref)


def _community_summaries(
    entities: list[dict[str, Any]],
    relations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    related = _relations_by_component(relations)
    communities = []
    entity_by_id = {str(item.get("id") or ""): item for item in entities}
    component_ids = _community_component_ids(entities, related)
    for component in component_ids:
        entity_rows = [entity_by_id[item] for item in component if item in entity_by_id]
        entity_relations = related.get(tuple(component), [])
        relation_text = " ".join(
            str(item.get("description") or "") for item in entity_relations
        )
        entity_text = " ".join(str(item.get("summary") or "") for item in entity_rows)
        summary = " ".join(
            item for item in (entity_text, relation_text) if item
        ).strip()
        labels = [
            str(item.get("label") or item.get("id") or "") for item in entity_rows
        ]
        source_backrefs = _unique(
            ref
            for item in entity_rows + entity_relations
            for ref in item.get("source_backrefs") or []
        )
        communities.append(
            {
                "id": f"community-{'-'.join(component)}",
                "label": ", ".join(label for label in labels if label),
                "summary": summary,
                "entity_ids": list(component),
                "source_backrefs": source_backrefs,
            }
        )
    return communities


def _relations_by_component(
    relations: list[dict[str, Any]],
) -> dict[tuple[str, ...], list[dict[str, Any]]]:
    components = _connected_components(relations)
    output: dict[tuple[str, ...], list[dict[str, Any]]] = {
        tuple(component): [] for component in components
    }
    for relation in relations:
        source = _slug(str(relation.get("source") or ""))
        target = _slug(str(relation.get("target") or ""))
        for component in output:
            if source in component or target in component:
                output[component].append(relation)
                break
    return output


def _community_component_ids(
    entities: list[dict[str, Any]],
    related: dict[tuple[str, ...], list[dict[str, Any]]],
) -> list[tuple[str, ...]]:
    components = list(related)
    for entity in entities:
        entity_id = str(entity.get("id") or "")
        if entity_id and not any(entity_id in component for component in components):
            components.append((entity_id,))
    components.sort(key=lambda item: (-len(item), item))
    return components


def _connected_components(relations: list[dict[str, Any]]) -> list[tuple[str, ...]]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for relation in relations:
        source = _slug(str(relation.get("source") or ""))
        target = _slug(str(relation.get("target") or ""))
        if source and target:
            adjacency[source].add(target)
            adjacency[target].add(source)
    components = []
    seen: set[str] = set()
    for node in sorted(adjacency):
        if node in seen:
            continue
        stack = [node]
        component = []
        while stack:
            current = stack.pop()
            if current in seen:
                continue
            seen.add(current)
            component.append(current)
            stack.extend(sorted(adjacency[current] - seen, reverse=True))
        components.append(tuple(sorted(component)))
    return components


def _claim(sentence: str, source_backrefs: list[str]) -> dict[str, Any]:
    return {
        "id": _slug(sentence)[:80] or "claim",
        "text": sentence,
        "source_backrefs": source_backrefs,
    }


def _entities(sentence: str) -> list[str]:
    return [
        _clean_entity(match)
        for match in re.findall(r"\b[A-Z][A-Za-z0-9_-]+\b", sentence)
    ]


def _metadata(doc: Any) -> dict[str, Any]:
    metadata = getattr(doc, "metadata", None)
    return metadata if isinstance(metadata, dict) else {}


def _text(doc: Any, metadata: dict[str, Any]) -> str:
    return str(getattr(doc, "text", None) or metadata.get("text") or "").strip()


def _source_backrefs(metadata: dict[str, Any]) -> list[str]:
    file_id = str(metadata.get("file_id") or metadata.get("source_id") or "").strip()
    page_label = str(metadata.get("page_label") or metadata.get("page") or "").strip()
    if file_id and page_label:
        return [f"{file_id}#page:{page_label}"]
    return [file_id] if file_id else []


def _sentences(text: str) -> list[str]:
    return [
        item.strip()
        for item in re.split(r"(?<=[.!?])\s+", str(text or ""))
        if item.strip()
    ]


def _clean_entity(value: str) -> str:
    return " ".join(str(value or "").strip(" .").split())


def _slug(value: str) -> str:
    return "-".join(
        token
        for token in re.findall(r"[a-zA-Z0-9]+", str(value or "").lower())
        if token
    )


def _unique(values: Any) -> list[str]:
    output: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in output:
            output.append(item)
    return output
