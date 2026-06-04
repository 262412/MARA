from __future__ import annotations

import re
from collections import defaultdict
from typing import Any, Iterable

GRAPH_BUILDER = "local_graph_builder_v1"


def local_graph_index_from_documents(documents: Iterable[Any]) -> dict[str, Any]:
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

    entity_rows = list(entities.values())
    return {
        "entities": entity_rows,
        "relations": relations,
        "claims": claims,
        "community_summaries": _community_summaries(entity_rows, relations),
        "metadata": {"graph_builder": GRAPH_BUILDER},
    }


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
