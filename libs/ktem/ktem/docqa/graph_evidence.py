from __future__ import annotations

from typing import Any

from .evidence_schema import EvidenceElement
from .query_planning import ensure_request_query_plan


def graph_items(
    request: Any,
    evidence_metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    expand_locators = bool(
        ensure_request_query_plan(request).constraints.get("requires_distinct_evidence")
    )
    items = [
        expanded
        for item in evidence_metadata.get("graph_evidence") or []
        for expanded in _graph_locator_items(
            _coerce_graph_item(item),
            expand=expand_locators,
        )
    ]
    graph_context = getattr(request, "graph_context", None)
    graph = graph_context.get("graph") if isinstance(graph_context, dict) else None
    if not isinstance(graph, dict):
        return items
    for node in graph.get("nodes") or []:
        if isinstance(node, dict):
            items.extend(
                _graph_locator_items(
                    _coerce_graph_item(node),
                    expand=expand_locators,
                )
            )
    return items


def _graph_locator_items(
    item: dict[str, Any],
    *,
    expand: bool,
) -> list[dict[str, Any]]:
    source_backrefs = [
        str(value or "").strip()
        for value in item.get("source_backrefs") or []
        if str(value or "").strip()
    ]
    if len(source_backrefs) == 1:
        return [_located_graph_item(item, source_backrefs[0])]
    if not expand or len(source_backrefs) < 2:
        return [item]
    return [_located_graph_item(item, source_ref) for source_ref in source_backrefs]


def _located_graph_item(
    item: dict[str, Any],
    source_backref: str,
) -> dict[str, Any]:
    if "#page:" in source_backref:
        source_id, page_label = source_backref.split("#page:", 1)
    elif "#source" in source_backref:
        source_id = source_backref.split("#source", 1)[0]
        page_label = ""
    else:
        source_id = source_backref
        page_label = ""
    located = dict(item)
    located["source_id"] = source_id.strip()
    located["page_label"] = page_label.strip()
    located["source_backrefs"] = [source_backref]
    located["element_id"] = ":".join(
        value
        for value in (
            str(item.get("element_id") or item.get("evidence_id") or "graph"),
            source_id,
            page_label,
        )
        if value
    )
    return located


def _coerce_graph_item(item: dict[str, Any]) -> dict[str, Any]:
    node_id = str(
        item.get("id") or item.get("element_id") or item.get("evidence_id") or ""
    ).strip()
    label = str(item.get("label") or item.get("source_name") or node_id).strip()
    return EvidenceElement(
        evidence_id=str(item.get("evidence_id") or f"graph:{node_id}").strip(),
        source_name=label,
        modality="graph",
        element_id=node_id,
        caption=label,
        text=str(item.get("summary") or item.get("text") or "").strip(),
        source_backrefs=_graph_source_backrefs(item),
        evidence_level="graph",
        metadata={"route": "graph_global"},
    ).as_dict()


def _graph_source_backrefs(item: dict[str, Any]) -> list[str]:
    page_refs = _graph_page_backrefs(item.get("support_pages"))
    if page_refs:
        return page_refs
    return [
        str(ref) for ref in item.get("source_ids") or item.get("source_backrefs") or []
    ]


def _graph_page_backrefs(support_pages: Any) -> list[str]:
    if not isinstance(support_pages, dict):
        return []
    refs: list[str] = []
    for source_id, pages in support_pages.items():
        source = str(source_id or "").strip()
        if not source:
            continue
        for page in pages or []:
            page_label = str(page or "").strip()
            if page_label:
                refs.append(f"{source}#page:{page_label}")
    return refs
