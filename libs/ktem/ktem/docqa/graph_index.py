from __future__ import annotations

import re
from typing import Any

GLOBAL_QUERY_TERMS = {
    "compare",
    "connect",
    "connection",
    "contrast",
    "overview",
    "relationship",
    "relationships",
    "summarize",
    "summary",
    "survey",
    "theme",
    "themes",
}


def select_graph_index_evidence(
    query: str,
    graph_context: dict[str, Any],
    *,
    max_items: int = 4,
) -> dict[str, Any]:
    graph_index = graph_context.get("graph_index")
    if not isinstance(graph_index, dict):
        return {}

    candidates = _graph_candidates(graph_index)
    if not candidates:
        return {}

    query_tokens = _tokens(query)
    global_query = bool(query_tokens & GLOBAL_QUERY_TERMS)
    ranked = _rank_candidates(candidates, query_tokens, global_query)
    selected = [item for _score, _index, item in ranked[:max_items]]
    if not selected:
        return {}

    source_ids = _unique(
        ref.split("#", 1)[0]
        for item in selected
        for ref in item.get("source_backrefs", [])
        if str(ref).strip()
    )
    return {
        "graph_backend": "local_graph_index",
        "graph_mode": "global" if global_query else "local",
        "graph_evidence": selected,
        "evidence_ids": [item["evidence_id"] for item in selected],
        "source_ids": source_ids,
        "page_coverage": _page_coverage(selected),
        "modality_counts": {"graph": len(selected)},
    }


def graph_answer_from_evidence(items: list[dict[str, Any]]) -> str:
    summaries = _unique(
        str(item.get("summary") or item.get("text") or "").strip() for item in items
    )
    return " ".join(summary.rstrip(".") + "." for summary in summaries if summary)


def _graph_candidates(graph_index: dict[str, Any]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    candidates.extend(
        _coerce_community(item) for item in graph_index.get("community_summaries") or []
    )
    candidates.extend(
        _coerce_entity(item) for item in graph_index.get("entities") or []
    )
    candidates.extend(
        _coerce_relation(item) for item in graph_index.get("relations") or []
    )
    candidates.extend(_coerce_claim(item) for item in graph_index.get("claims") or [])
    return [item for item in candidates if item.get("summary") or item.get("text")]


def _coerce_community(item: dict[str, Any]) -> dict[str, Any]:
    item_id = _item_id(item, "community")
    return _graph_item(
        evidence_id=f"graph-community:{item_id}",
        item_id=item_id,
        label=str(item.get("label") or item.get("title") or item_id),
        summary=str(item.get("summary") or item.get("text") or ""),
        kind="community",
        item=item,
    )


def _coerce_entity(item: dict[str, Any]) -> dict[str, Any]:
    item_id = _item_id(item, "entity")
    return _graph_item(
        evidence_id=f"graph-entity:{item_id}",
        item_id=item_id,
        label=str(
            item.get("label") or item.get("entity") or item.get("name") or item_id
        ),
        summary=str(item.get("summary") or item.get("description") or ""),
        kind="entity",
        item=item,
    )


def _coerce_relation(item: dict[str, Any]) -> dict[str, Any]:
    item_id = _item_id(item, "relation")
    source = str(item.get("source") or "")
    target = str(item.get("target") or "")
    label = str(item.get("label") or f"{source} -> {target}".strip())
    return _graph_item(
        evidence_id=f"graph-relation:{item_id}",
        item_id=item_id,
        label=label,
        summary=str(item.get("summary") or item.get("description") or ""),
        kind="relation",
        item=item,
    )


def _coerce_claim(item: dict[str, Any]) -> dict[str, Any]:
    item_id = _item_id(item, "claim")
    text = str(item.get("text") or item.get("claim") or item.get("summary") or "")
    return _graph_item(
        evidence_id=f"graph-claim:{item_id}",
        item_id=item_id,
        label=str(item.get("label") or item_id),
        summary=text,
        kind="claim",
        item=item,
    )


def _graph_item(
    *,
    evidence_id: str,
    item_id: str,
    label: str,
    summary: str,
    kind: str,
    item: dict[str, Any],
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "id": item_id,
        "label": label,
        "summary": summary.strip(),
        "kind": kind,
        "source_backrefs": _source_backrefs(item),
        "support_pages": dict(item.get("support_pages") or {}),
    }


def _item_id(item: dict[str, Any], prefix: str) -> str:
    item_id = str(item.get("id") or item.get("element_id") or "").strip()
    if item_id:
        return item_id
    label = str(item.get("label") or item.get("text") or prefix).strip()
    slug = "-".join(_tokens(label))[:80]
    return slug or prefix


def _source_backrefs(item: dict[str, Any]) -> list[str]:
    refs = [
        str(ref).strip()
        for ref in item.get("source_backrefs") or item.get("source_ids") or []
        if str(ref).strip()
    ]
    if refs:
        return refs
    return _page_backrefs(item.get("support_pages"))


def _page_backrefs(support_pages: Any) -> list[str]:
    if not isinstance(support_pages, dict):
        return []
    refs: list[str] = []
    for source_id, pages in support_pages.items():
        source = str(source_id or "").strip()
        for page in pages or []:
            page_label = str(page or "").strip()
            if source and page_label:
                refs.append(f"{source}#page:{page_label}")
    return refs


def _rank_candidates(
    candidates: list[dict[str, Any]], query_tokens: set[str], global_query: bool
) -> list[tuple[int, int, dict[str, Any]]]:
    ranked = [
        (_score_candidate(item, query_tokens, global_query), index, item)
        for index, item in enumerate(candidates)
    ]
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return ranked


def _score_candidate(
    item: dict[str, Any], query_tokens: set[str], global_query: bool
) -> int:
    score = len(query_tokens & _tokens(f"{item.get('label')} {item.get('summary')}"))
    if item.get("kind") == "community" and global_query:
        score += 6
    if item.get("kind") in {"entity", "relation", "claim"} and not global_query:
        score += 2
    return score


def _page_coverage(items: list[dict[str, Any]]) -> list[str]:
    pages: list[str] = []
    for item in items:
        for ref in item.get("source_backrefs", []):
            if "#page:" not in str(ref):
                continue
            page = str(ref).rsplit("#page:", 1)[-1]
            if page and page not in pages:
                pages.append(page)
    return pages


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9]+", str(value or "").lower())
        if len(token) > 2
    }


def _unique(values: Any) -> list[str]:
    output: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in output:
            output.append(item)
    return output
