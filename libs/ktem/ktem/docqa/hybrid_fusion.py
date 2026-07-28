from __future__ import annotations

import re
from typing import Any

from .evidence_field_values import retrieval_lineage_values
from .evidence_identity import identity_of
from .retrieval_adequacy import financial_statement_match_count

FUSION_RANKER = "retriever_reciprocal_rank_fusion_v2"
WEIGHTED_RANKER = "weighted_cross_modal_v1"
RRF_RANKER = FUSION_RANKER
MODALITY_WEIGHTS = {
    "text": 1.0,
    "page_image": 1.2,
    "figure": 1.2,
    "formula": 1.2,
    "slide": 1.2,
    "table": 1.1,
    "graph": 0.9,
}
MODALITY_TERMS = {
    "page_image": {"chart", "diagram", "figure", "image", "plot", "slide", "visual"},
    "figure": {"chart", "diagram", "figure", "image", "plot", "visual"},
    "formula": {"equation", "formula", "latex", "math"},
    "slide": {"deck", "presentation", "ppt", "pptx", "slide"},
    "table": {"column", "row", "table"},
}


def fuse_hybrid_evidence(
    query: str,
    items: list[dict[str, Any]],
    *,
    strategy: str = "",
    learned_ranker: Any = None,
    domain: str | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if learned_ranker is not None:
        return _fuse_with_learned_ranker(query, items, learned_ranker, domain=domain)
    if str(strategy or "").strip().lower() == "weighted":
        return _fuse_with_weighted_scores(query, items, domain=domain)
    if str(strategy or "").strip().lower() == "rrf":
        return _fuse_with_rrf(query, items, domain=domain)
    return _fuse_with_rrf(query, items, domain=domain)


def _document_complex_text_guard(
    domain: str | None,
    selected_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    trace: dict[str, Any] = {
        "best_single_route": _best_single_route(selected_rows),
        "fusion_selected_route": _first_row_route(selected_rows),
        "fallback_route": "",
        "locator_confidence_by_route": _locator_confidence_by_route(selected_rows),
    }
    if str(domain or "").strip().lower() not in {"document_complex", "mmdocrag"}:
        return selected_rows, trace
    text_rows = [
        row
        for row in selected_rows
        if str(row.get("group") or "") == "text" and _locator_confidence(row) >= 1.0
    ]
    if not text_rows:
        return selected_rows, trace
    text_page = _row_page_key(text_rows[0])
    cross_page_visual = any(
        str(row.get("group") or "") in {"page_image", "figure", "slide"}
        and _row_page_key(row) != text_page
        for row in selected_rows
    )
    trace["cross_page_visual_preserved"] = cross_page_visual
    return selected_rows, trace


def _drop_low_coverage_element_rows(
    domain: str | None,
    selected_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if str(domain or "").strip().lower() not in {"document_complex", "mmdocrag"}:
        return selected_rows, {"dropped_low_coverage_element_count": 0}
    kept: list[dict[str, Any]] = []
    dropped_count = 0
    for row in selected_rows:
        if str(row.get("group") or "") == "element" and not _element_row_has_coverage(
            row
        ):
            dropped_count += 1
            continue
        kept.append(row)
    return kept, {"dropped_low_coverage_element_count": dropped_count}


def _element_row_has_coverage(row: dict[str, Any]) -> bool:
    item = dict(row.get("item") or {})
    has_locator = bool(
        str(item.get("source_id") or item.get("file_id") or "").strip()
        and str(item.get("page_label") or item.get("page_number") or "").strip()
    )
    has_text_or_ocr = bool(
        str(
            item.get("text") or item.get("ocr_text") or item.get("caption") or ""
        ).strip()
    )
    return has_locator and has_text_or_ocr


def _best_single_route(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return ""
    ranked = sorted(
        rows,
        key=lambda row: (
            -_locator_confidence(row),
            -float(row.get("final_score") or 0.0),
            int(row.get("index") or 0),
        ),
    )
    return str(ranked[0].get("group") or "")


def _locator_confidence_by_route(rows: list[dict[str, Any]]) -> dict[str, float]:
    confidences: dict[str, float] = {}
    for row in rows:
        route = str(row.get("group") or "")
        if not route:
            continue
        confidences[route] = max(confidences.get(route, 0.0), _locator_confidence(row))
    return {key: round(value, 4) for key, value in confidences.items()}


def _locator_confidence(row: dict[str, Any]) -> float:
    source_id, page_label = _row_page_key(row)
    if source_id and page_label:
        return 1.0
    if source_id or page_label:
        return 0.5
    return 0.0


def _row_page_key(row: dict[str, Any]) -> tuple[str, str]:
    item = dict(row.get("item") or {})
    return (
        str(item.get("source_id") or item.get("file_id") or "").strip(),
        str(item.get("page_label") or item.get("page_number") or "").strip(),
    )


def _first_row_route(rows: list[dict[str, Any]]) -> str:
    return str(rows[0].get("group") or "") if rows else ""


def _first_item_route(items: list[dict[str, Any]]) -> str:
    if not items:
        return ""
    metadata = dict(items[0].get("metadata") or {})
    confidence = metadata.get("evidence_confidence")
    if isinstance(confidence, dict):
        return str(confidence.get("route") or "")
    return str(items[0].get("modality") or "")


def _fuse_with_weighted_scores(
    query: str,
    items: list[dict[str, Any]],
    *,
    domain: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    scored_items = []
    item_scores: dict[str, float] = {}
    for index, item in enumerate(items):
        score, components = _fusion_score(query, item, domain=domain)
        scored = _with_fusion_metadata(item, score, components)
        item_scores[identity_of(scored).key] = score
        scored_items.append((score, index, scored))

    scored_items.sort(key=lambda row: (-row[0], row[1]))
    return [item for _, _, item in scored_items], {
        "ranker": WEIGHTED_RANKER,
        "modality_weights": dict(MODALITY_WEIGHTS),
        "item_scores": item_scores,
    }


def _fuse_with_rrf(
    query: str,
    items: list[dict[str, Any]],
    *,
    domain: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    weighted_rows = []
    for index, item in enumerate(items):
        score, components = _fusion_score(query, item, domain=domain)
        weighted_rows.append((score, index, item, components))

    rrf_scores, contributions, retriever_lists = _rrf_scores_by_item(weighted_rows)
    scored_items = []
    item_scores: dict[str, float] = {}
    for score, index, item, components in weighted_rows:
        identity = identity_of(item).key
        rrf_score, rrf_components = _rrf_item_score(
            identity,
            components,
            rrf_scores,
            contributions,
        )
        scored = _with_fusion_metadata(item, rrf_score, rrf_components)
        item_scores[identity] = rrf_score
        scored_items.append((rrf_score, index, scored))

    scored_items.sort(key=lambda row: (-row[0], row[1]))
    max_score = scored_items[0][0] if scored_items else 0.0
    fused = [
        _with_evidence_confidence(
            item,
            route=_modality_group(item),
            normalized_score=score / max_score if max_score else 0.0,
            score_margin=0.0,
            pre_fusion_rank=rank,
            normalized_rank=rank,
        )
        for rank, (score, _index, item) in enumerate(scored_items, start=1)
    ]
    rows = [
        {
            "item": item,
            "group": _modality_group(item),
            "final_score": score,
            "index": index,
        }
        for score, index, item in scored_items
    ]
    rows, element_gate_trace = _drop_low_coverage_element_rows(domain, rows)
    rows, guard_trace = _document_complex_text_guard(domain, rows)
    allowed = set()
    for row in rows:
        row_item = row.get("item")
        if isinstance(row_item, dict):
            allowed.add(identity_of(row_item).key)
    fused = [item for item in fused if identity_of(item).key in allowed]
    trace = {
        "ranker": RRF_RANKER,
        "rrf_k": 60,
        "retriever_lists": retriever_lists,
        "item_scores": item_scores,
        "dropped_noise_count": max(0, len(items) - len(fused)),
    }
    trace.update(element_gate_trace)
    trace.update(guard_trace)
    return fused, trace


def _rrf_item_score(
    identity: str,
    components: dict[str, float],
    scores: dict[str, float],
    contributions: dict[str, dict[str, float]],
) -> tuple[float, dict[str, Any]]:
    relevance_tiebreak = min(
        0.0005,
        (
            float(components.get("lexical_overlap") or 0.0)
            + float(components.get("modality_intent") or 0.0)
        )
        * 0.0001,
    )
    score = round(scores.get(identity, 0.0), 6)
    score += round(relevance_tiebreak, 6)
    score += round(
        float(components.get("finance_statement_match") or 0.0) * 0.001,
        6,
    )
    trace: dict[str, Any] = dict(components)
    trace["rrf_score"] = score
    trace["relevance_tiebreak"] = round(relevance_tiebreak, 6)
    trace["rrf_contributions"] = contributions.get(identity, {})
    return score, trace


def _fuse_with_learned_ranker(
    query: str,
    items: list[dict[str, Any]],
    ranker: Any,
    *,
    domain: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ranker_name = str(getattr(ranker, "name", None) or ranker.__class__.__name__)
    scored_items = []
    item_scores: dict[str, float] = {}
    for index, item in enumerate(items):
        weighted_score, components = _fusion_score(query, item, domain=domain)
        learned_score = round(float(ranker.score(query, item) or 0.0), 4)
        components = dict(components)
        components["learned_score"] = learned_score
        components["weighted_score"] = weighted_score
        scored = _with_fusion_metadata(
            item,
            learned_score,
            components,
            reranker_backend=ranker_name,
        )
        item_scores[identity_of(scored).key] = learned_score
        scored_items.append((learned_score, index, scored))

    scored_items.sort(key=lambda row: (-row[0], row[1]))
    reranked = [
        _with_reranker_lineage(item, ranker_name, rank)
        for rank, (_score, _index, item) in enumerate(scored_items, start=1)
    ]
    return reranked, {
        "ranker": ranker_name,
        "ranker_type": "learned_cross_modal",
        "item_scores": item_scores,
    }


def _fusion_score(
    query: str,
    item: dict[str, Any],
    *,
    domain: str | None,
) -> tuple[float, dict[str, float]]:
    modality = str(item.get("modality") or "text").strip() or "text"
    lexical = float(len(_tokens(query) & _item_tokens(item)))
    modality_weight = float(MODALITY_WEIGHTS.get(modality, 1.0))
    modality_intent = _modality_intent_score(query, modality)
    retriever_score = _retriever_score(item)
    finance_statement_match = float(
        financial_statement_match_count(query, _item_text(item), domain=domain)
    )
    finance_statement_score = finance_statement_match * 6.0
    score = round(
        modality_weight
        + lexical
        + modality_intent
        + retriever_score
        + finance_statement_score,
        4,
    )
    return score, {
        "lexical_overlap": lexical,
        "modality_weight": modality_weight,
        "modality_intent": modality_intent,
        "retriever_score": retriever_score,
        "finance_statement_match": finance_statement_match,
    }


def _with_fusion_metadata(
    item: dict[str, Any],
    score: float,
    components: dict[str, float],
    *,
    reranker_backend: str = "",
) -> dict[str, Any]:
    scored = dict(item)
    metadata = dict(scored.get("metadata") or {})
    metadata["hybrid_fusion_score"] = score
    metadata["hybrid_fusion_components"] = components
    if reranker_backend:
        metadata["reranker_backend"] = reranker_backend
        metadata["reranker_score"] = score
    scored["metadata"] = metadata
    return scored


def _with_reranker_lineage(
    item: dict[str, Any],
    backend: str,
    rank: int,
) -> dict[str, Any]:
    scored = dict(item)
    metadata = dict(scored.get("metadata") or {})
    metadata["reranker_backend"] = backend
    metadata["reranker_input_identity"] = identity_of(item).key
    metadata["reranker_rank"] = rank
    scored["metadata"] = metadata
    return scored


def _rrf_scores_by_item(
    weighted_rows: list[tuple[float, int, dict[str, Any], dict[str, float]]],
) -> tuple[dict[str, float], dict[str, dict[str, float]], list[str]]:
    scores: dict[str, float] = {}
    contributions: dict[str, dict[str, float]] = {}
    rank_lists = _retriever_rank_lists(weighted_rows)
    for retriever, rows in rank_lists.items():
        ranked = sorted(rows, key=lambda row: (-row[0], row[1]))
        seen_identities: set[str] = set()
        unique_ranked = []
        for row in ranked:
            identity = identity_of(row[2]).key
            if identity in seen_identities:
                continue
            seen_identities.add(identity)
            unique_ranked.append(row)
        for rank, (_score, index, item, _components) in enumerate(
            unique_ranked,
            start=1,
        ):
            identity = identity_of(item).key
            contribution = 1.0 / (60 + rank)
            scores[identity] = scores.get(identity, 0.0) + contribution
            contributions.setdefault(identity, {})[retriever] = round(contribution, 6)
    return scores, contributions, sorted(rank_lists)


def _retriever_rank_lists(
    weighted_rows: list[tuple[float, int, dict[str, Any], dict[str, float]]],
) -> dict[str, list[tuple[float, int, dict[str, Any], dict[str, float]]]]:
    rank_lists: dict[
        str,
        list[tuple[float, int, dict[str, Any], dict[str, float]]],
    ] = {}
    for weighted_score, index, item, components in weighted_rows:
        lineage_scores = _lineage_retriever_scores(item)
        if lineage_scores:
            for retriever, score in lineage_scores.items():
                rank_lists.setdefault(retriever, []).append(
                    (score, index, item, components)
                )
            continue
        explicit = _explicit_retriever_scores(item)
        if explicit:
            for retriever, score in explicit.items():
                rank_lists.setdefault(retriever, []).append(
                    (score, index, item, components)
                )
            continue
        fallback = _modality_group(item)
        rank_lists.setdefault(fallback, []).append(
            (weighted_score, index, item, components)
        )
    return rank_lists


def _lineage_retriever_scores(item: dict[str, Any]) -> dict[str, float]:
    metadata = dict(item.get("metadata") or {})
    scores: dict[str, float] = {}
    for entry in retrieval_lineage_values(item, metadata):
        retriever = str(entry.get("retriever_name") or "").strip()
        if not retriever:
            continue
        round_id = str(entry.get("round_id") or "").strip() or "unknown"
        query_id = str(entry.get("query_id") or "").strip() or "default"
        rank_list = f"{retriever}|round:{round_id}|query:{query_id}"
        raw_rank = _positive_int(entry.get("raw_rank"))
        if raw_rank is not None:
            score = 1.0 / raw_rank
        else:
            score = _float_or_zero(entry.get("raw_score"))
        scores[rank_list] = max(scores.get(rank_list, float("-inf")), score)
    return scores


def _explicit_retriever_scores(item: dict[str, Any]) -> dict[str, float]:
    metadata = dict(item.get("metadata") or {})
    fields = {
        "text": ("retriever_score",),
        "visual": ("visual_retriever_score",),
        "element": ("element_retriever_score",),
        "graph": ("graph_retriever_score",),
    }
    scores: dict[str, float] = {}
    for retriever, names in fields.items():
        for name in names:
            value = metadata.get(name, item.get(name))
            if value in (None, ""):
                continue
            scores[retriever] = float(value)
            break
    return scores


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _float_or_zero(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _modality_group(item: dict[str, Any]) -> str:
    modality = str(item.get("modality") or "text").strip() or "text"
    if modality in {"text", "page_image", "graph"}:
        return modality
    return "element"


def _with_evidence_confidence(
    item: dict[str, Any],
    *,
    route: str,
    normalized_score: float,
    score_margin: float,
    pre_fusion_rank: int,
    normalized_rank: int,
) -> dict[str, Any]:
    scored = dict(item)
    metadata = dict(scored.get("metadata") or {})
    has_locator = bool(scored.get("source_id") and scored.get("page_label"))
    has_text_or_ocr = bool(
        str(
            scored.get("text") or scored.get("ocr_text") or scored.get("vlm_text") or ""
        ).strip()
    )
    locator_confidence = 1.0 if has_locator else 0.5 if scored.get("source_id") else 0.0
    metadata["evidence_confidence"] = {
        "route": route,
        "normalized_score": round(normalized_score, 4),
        "score_margin": score_margin,
        "locator_confidence": locator_confidence,
        "has_text_or_ocr": has_text_or_ocr,
        "citation_locator_quality": locator_confidence,
        "pre_fusion_rank": pre_fusion_rank,
        "normalized_rank": normalized_rank,
    }
    scored["metadata"] = metadata
    return scored


def _modality_intent_score(query: str, modality: str) -> float:
    query_tokens = _tokens(query)
    return 0.5 if query_tokens & MODALITY_TERMS.get(modality, set()) else 0.0


def _retriever_score(item: dict[str, Any]) -> float:
    metadata = dict(item.get("metadata") or {})
    for key in (
        "visual_retriever_score",
        "element_retriever_score",
        "retriever_score",
    ):
        value = metadata.get(key)
        if value is not None and value != "":
            return round(float(str(value)) * 10.0, 4)
    return 0.0


def _item_tokens(item: dict[str, Any]) -> set[str]:
    return _tokens(_item_text(item))


def _item_text(item: dict[str, Any]) -> str:
    metadata = dict(item.get("metadata") or {})
    metadata_text = " ".join(
        str(part)
        for value in metadata.values()
        for part in (value if isinstance(value, list) else [value])
    )
    return (
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
        + " "
        + metadata_text
    )


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-zA-Z0-9]+", str(value or "").lower())
        if len(token) > 2
    }
