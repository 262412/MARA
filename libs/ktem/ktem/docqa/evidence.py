from __future__ import annotations

import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from typing import Any

from .hybrid_fusion import fuse_hybrid_evidence
from .m3docrag import select_page_first_evidence


@dataclass(frozen=True)
class EvidenceElement:
    evidence_id: str
    source_id: str = ""
    source_name: str = ""
    page_label: str = ""
    modality: str = "text"
    element_id: str = ""
    bbox: Any = None
    caption: str = ""
    text: str = ""
    ocr_text: str = ""
    vlm_text: str = ""
    source_backrefs: list[str] = field(default_factory=list)
    evidence_level: str = "page"
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceBundle:
    route: str
    items: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_evidence_bundle(
    route: str,
    request: Any,
    evidence_metadata: dict[str, Any],
) -> EvidenceBundle:
    base_items = [
        _coerce_item(item) for item in evidence_metadata.get("evidence") or []
    ]
    items = (
        [] if route in {"doc_page_image", "doc_element", "graph_global"} else base_items
    )
    if route in {"doc_page_image", "hybrid"}:
        page_items = _page_image_items(evidence_metadata)
        page_item = _page_image_item(request, route)
        if page_item is not None:
            page_items.append(page_item)
        items.extend(_rank_route_items(page_items, request, "doc_page_image"))
    if route in {"doc_element", "hybrid"}:
        element_scores = dict(evidence_metadata.get("element_retriever_scores") or {})
        element_items = [
            _coerce_item(_with_element_retriever_score(item, element_scores))
            for item in evidence_metadata.get("element_index") or []
        ]
        element_items.extend(
            _coerce_item(item) for item in evidence_metadata.get("elements") or []
        )
        items.extend(_rank_route_items(element_items, request, "doc_element"))
    if route in {"graph_global", "hybrid"}:
        items.extend(_graph_items(request, evidence_metadata))

    deduped = _dedupe_items(items)
    m3docrag_trace: dict[str, Any] | None = None
    hybrid_fusion_trace: dict[str, Any] | None = None
    if route == "hybrid":
        deduped, hybrid_fusion_trace = fuse_hybrid_evidence(
            str(getattr(request, "prompt", "") or ""),
            deduped,
            strategy=str(evidence_metadata.get("hybrid_fusion_strategy") or ""),
            learned_ranker=evidence_metadata.get("hybrid_fusion_ranker"),
        )
        deduped, m3docrag_trace = select_page_first_evidence(
            str(getattr(request, "prompt", "") or ""),
            deduped,
        )
    metadata = dict(evidence_metadata)
    metadata["modality_counts"] = dict(Counter(item["modality"] for item in deduped))
    metadata["evidence"] = deduped
    if m3docrag_trace is not None:
        metadata["m3docrag_trace"] = m3docrag_trace
    if hybrid_fusion_trace is not None:
        metadata["hybrid_fusion_trace"] = hybrid_fusion_trace
    return EvidenceBundle(route=route, items=deduped, metadata=metadata)


def _page_image_items(evidence_metadata: dict[str, Any]) -> list[dict[str, Any]]:
    scores = dict(evidence_metadata.get("visual_retriever_scores") or {})
    return [
        _coerce_item(_with_visual_retriever_score(item, scores))
        for item in evidence_metadata.get("page_image_index") or []
    ]


def _with_visual_retriever_score(
    item: dict[str, Any], scores: dict[str, Any]
) -> dict[str, Any]:
    evidence_id = str(item.get("evidence_id") or "").strip()
    if evidence_id not in scores:
        return item
    scored = dict(item)
    metadata = dict(scored.get("metadata") or {})
    metadata["visual_retriever_score"] = float(scores[evidence_id])
    scored["metadata"] = metadata
    return scored


def _with_element_retriever_score(
    item: dict[str, Any], scores: dict[str, Any]
) -> dict[str, Any]:
    evidence_id = str(item.get("evidence_id") or "").strip()
    if evidence_id not in scores:
        return item
    scored = dict(item)
    metadata = dict(scored.get("metadata") or {})
    metadata["element_retriever_score"] = float(scores[evidence_id])
    scored["metadata"] = metadata
    return scored


def _coerce_item(item: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(item.get("metadata") or {})
    file_id = str(item.get("file_id") or item.get("source_id") or "").strip()
    page_label = str(item.get("page_label") or item.get("page") or "").strip()
    modality = str(
        item.get("modality") or item.get("element_type") or item.get("type") or "text"
    ).strip()
    backrefs = list(item.get("source_backrefs") or [])
    if not backrefs and file_id and page_label:
        backrefs = [f"{file_id}#page:{page_label}"]
    return EvidenceElement(
        evidence_id=str(item.get("evidence_id") or item.get("doc_id") or "").strip(),
        source_id=file_id,
        source_name=str(item.get("file_name") or item.get("source_name") or "").strip(),
        page_label=page_label,
        modality=modality or "text",
        element_id=str(item.get("element_id") or "").strip(),
        bbox=item.get("bbox"),
        caption=str(item.get("caption") or "").strip(),
        text=str(item.get("text") or item.get("content") or "").strip(),
        ocr_text=str(item.get("ocr_text") or "").strip(),
        vlm_text=str(item.get("vlm_text") or "").strip(),
        source_backrefs=backrefs,
        evidence_level=str(item.get("evidence_level") or "page").strip(),
        metadata=metadata,
    ).as_dict()


def _page_image_item(request: Any, route: str) -> dict[str, Any] | None:
    file_id = str(getattr(request, "active_file_id", "") or "").strip()
    file_name = str(getattr(request, "active_file_name", "") or "").strip()
    page_number = getattr(request, "page_number", None)
    if not file_id or page_number is None or page_number == "":
        return None
    page_label = str(max(1, int(page_number)))
    text = str(getattr(request, "selected_text", "") or "").strip()
    return EvidenceElement(
        evidence_id=f"page-image:{file_id}:{page_label}",
        source_id=file_id,
        source_name=file_name,
        page_label=page_label,
        modality="page_image",
        text=text,
        ocr_text=text,
        source_backrefs=[f"{file_id}#page:{page_label}"],
        metadata={"route": route},
    ).as_dict()


def _graph_items(
    request: Any, evidence_metadata: dict[str, Any]
) -> list[dict[str, Any]]:
    items = [
        _coerce_graph_item(item)
        for item in evidence_metadata.get("graph_evidence") or []
    ]
    graph_context = getattr(request, "graph_context", None)
    graph = graph_context.get("graph") if isinstance(graph_context, dict) else None
    if not isinstance(graph, dict):
        return items
    for node in graph.get("nodes") or []:
        if isinstance(node, dict):
            items.append(_coerce_graph_item(node))
    return items


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


def _dedupe_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        key = (
            str(item.get("evidence_id") or ""),
            str(item.get("modality") or ""),
            str(item.get("element_id") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


_MODALITY_TERMS = {
    "page_image": {"chart", "diagram", "figure", "image", "plot", "slide", "visual"},
    "figure": {"chart", "diagram", "figure", "image", "plot", "visual"},
    "table": {"column", "row", "table"},
    "formula": {"equation", "formula", "latex", "math"},
    "slide": {"deck", "presentation", "ppt", "pptx", "slide"},
}


def _rank_route_items(
    items: list[dict[str, Any]], request: Any, route: str
) -> list[dict[str, Any]]:
    query_tokens = _tokens(
        f"{getattr(request, 'prompt', '')} {getattr(request, 'selected_text', '')}"
    )
    if not query_tokens:
        return items
    ranked = [
        (_route_item_score(item, request, query_tokens, route), index, item)
        for index, item in enumerate(items)
    ]
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return [item for _, _, item in ranked]


def _route_item_score(
    item: dict[str, Any],
    request: Any,
    query_tokens: set[str],
    route: str,
) -> int:
    score = len(query_tokens & _item_tokens(item))
    modality = str(item.get("modality") or "").strip()
    score += _visual_retriever_score(item)
    score += 3 * len(query_tokens & _metadata_tokens(item))
    if query_tokens & _MODALITY_TERMS.get(modality, set()):
        score += 8
    if route == "doc_page_image" and modality == "page_image":
        score += 2
    if route == "doc_element" and modality not in {"", "page_image", "text"}:
        score += 2

    active_file_id = str(getattr(request, "active_file_id", "") or "").strip()
    source_id = str(item.get("source_id") or "").strip()
    if active_file_id and source_id == active_file_id:
        score += 6
    elif source_id in _selected_file_ids(request):
        score += 3

    page_number = getattr(request, "page_number", None)
    if page_number is not None and str(item.get("page_label") or "") == str(
        page_number
    ):
        score += 4
    return score


def _selected_file_ids(request: Any) -> set[str]:
    return {
        str(item).strip()
        for item in getattr(request, "selected_file_ids", None) or []
        if str(item).strip()
    }


def _item_tokens(item: dict[str, Any]) -> set[str]:
    return _tokens(
        " ".join(
            str(item.get(key) or "")
            for key in (
                "caption",
                "element_id",
                "modality",
                "ocr_text",
                "source_name",
                "text",
                "vlm_text",
            )
        )
    )


def _metadata_tokens(item: dict[str, Any]) -> set[str]:
    metadata = dict(item.get("metadata") or {})
    values: list[Any] = [
        metadata.get("late_interaction_tokens"),
        metadata.get("visual_retriever"),
    ]
    return _tokens(
        " ".join(
            str(part)
            for value in values
            for part in (value if isinstance(value, list) else [value])
        )
    )


def _visual_retriever_score(item: dict[str, Any]) -> int:
    metadata = dict(item.get("metadata") or {})
    return int(float(metadata.get("visual_retriever_score") or 0.0) * 100)


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9]+", str(value or "").lower())
        if len(token) > 2
    }
