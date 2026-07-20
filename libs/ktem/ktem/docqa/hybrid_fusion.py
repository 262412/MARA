from __future__ import annotations

import re
from typing import Any

from .retrieval_adequacy import financial_statement_match_count

FUSION_RANKER = "modality_normalized_rrf_v1"
WEIGHTED_RANKER = "weighted_cross_modal_v1"
RRF_RANKER = "reciprocal_rank_fusion_v1"
MODALITY_TOP_K = {"text": 30, "page_image": 20, "element": 20, "graph": 20}
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
    return _fuse_with_modality_normalized_rrf(query, items, domain=domain)


def _fuse_with_modality_normalized_rrf(
    query: str,
    items: list[dict[str, Any]],
    *,
    domain: str | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = _fusion_rows(query, items, domain=domain)
    selected_rows = _selected_normalized_rrf_rows(query, rows)
    selected_rows, element_gate_trace = _drop_low_coverage_element_rows(
        domain,
        selected_rows,
    )
    selected_rows, guard_trace = _document_complex_text_guard(
        domain,
        selected_rows,
    )
    selected_rows.sort(key=lambda row: (-row["final_score"], row["index"]))
    fused, item_scores = _materialize_normalized_rows(rows, selected_rows)
    trace = _normalized_rrf_trace(items, fused, item_scores)
    trace.update(element_gate_trace)
    trace.update(guard_trace)
    return fused, trace


def _fusion_rows(
    query: str,
    items: list[dict[str, Any]],
    *,
    domain: str | None,
) -> list[dict[str, Any]]:
    rows = []
    for index, item in enumerate(items):
        score, components = _fusion_score(query, item, domain=domain)
        rows.append(
            {
                "score": score,
                "index": index,
                "item": item,
                "components": components,
                "group": _modality_group(item),
            }
        )
    return rows


def _selected_normalized_rrf_rows(
    query: str, rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    selected_rows = []
    for group, group_rows in _dict_rows_by_modality(rows).items():
        ranked = sorted(group_rows, key=lambda row: (-row["score"], row["index"]))
        for rank, row in enumerate(ranked[: MODALITY_TOP_K.get(group, 1)], start=1):
            selected_rows.append(_normalized_rrf_row(query, group, ranked, rank, row))
    return selected_rows


def _normalized_rrf_row(
    query: str,
    group: str,
    ranked: list[dict[str, Any]],
    rank: int,
    row: dict[str, Any],
) -> dict[str, Any]:
    normalized = _normalized_group_score(ranked, row)
    rrf_score = 1.0 / (60 + rank)
    final_score = round(
        rrf_score + normalized * 0.001 + _modality_preference_bias(query, str(group)),
        6,
    )
    components = dict(row["components"])
    components.update(
        {
            "rrf_score": round(rrf_score, 6),
            "normalized_score": round(normalized, 4),
            "pre_fusion_rank": rank,
            "modality_group": str(group),
        }
    )
    output = dict(row)
    output["final_score"] = final_score
    output["components"] = components
    output["normalized_score"] = round(normalized, 4)
    output["pre_fusion_rank"] = rank
    return output


def _normalized_group_score(ranked: list[dict[str, Any]], row: dict[str, Any]) -> float:
    max_score = float(ranked[0]["score"] or 0.0) if ranked else 0.0
    min_score = float(ranked[-1]["score"] or 0.0) if ranked else 0.0
    score_range = max(max_score - min_score, 0.0)
    if score_range == 0.0:
        return 1.0
    return (float(row["score"]) - min_score) / score_range


def _materialize_normalized_rows(
    rows: list[dict[str, Any]], selected_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    fused = []
    item_scores: dict[str, float] = {}
    for normalized_rank, row in enumerate(selected_rows, start=1):
        item = _with_fusion_metadata(
            row["item"],
            float(row["final_score"]),
            row["components"],
        )
        item = _with_evidence_confidence(
            item,
            route=str(row["group"]),
            normalized_score=float(row["normalized_score"]),
            score_margin=_score_margin(rows, row),
            pre_fusion_rank=int(row["pre_fusion_rank"]),
            normalized_rank=normalized_rank,
        )
        evidence_id = str(item.get("evidence_id") or f"item-{row['index']}")
        item_scores[evidence_id] = float(row["final_score"])
        fused.append(item)
    return fused, item_scores


def _normalized_rrf_trace(
    items: list[dict[str, Any]],
    fused: list[dict[str, Any]],
    item_scores: dict[str, float],
) -> dict[str, Any]:
    return {
        "ranker": FUSION_RANKER,
        "selected_top_k": {
            key: MODALITY_TOP_K[key] for key in ("text", "page_image", "element")
        },
        "dropped_noise_count": max(0, len(items) - len(fused)),
        "fallback_route": "",
        "best_single_route": "",
        "fusion_selected_route": _first_item_route(fused),
        "locator_confidence_by_route": {},
        "item_scores": item_scores,
    }


def _document_complex_text_guard(
    domain: str | None,
    selected_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    trace = {
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
    noisy_cross_page_visual = any(
        str(row.get("group") or "") in {"page_image", "figure", "slide"}
        and _row_page_key(row) != text_page
        for row in selected_rows
    )
    if not noisy_cross_page_visual:
        return selected_rows, trace
    trace["fallback_route"] = "text"
    trace["best_single_route"] = "text"
    return text_rows, trace


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
        item_scores[str(scored.get("evidence_id") or f"item-{index}")] = score
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

    rrf_scores = _rrf_scores_by_item(weighted_rows)
    scored_items = []
    item_scores: dict[str, float] = {}
    for score, index, item, components in weighted_rows:
        evidence_id = str(item.get("evidence_id") or f"item-{index}")
        rrf_score = round(rrf_scores.get(evidence_id, 0.0), 6)
        rrf_score += round(score * 0.0001, 6)
        rrf_components = dict(components)
        rrf_components["rrf_score"] = rrf_score
        scored = _with_fusion_metadata(item, rrf_score, rrf_components)
        item_scores[evidence_id] = rrf_score
        scored_items.append((rrf_score, index, scored))

    scored_items.sort(key=lambda row: (-row[0], row[1]))
    return [item for _, _, item in scored_items], {
        "ranker": RRF_RANKER,
        "rrf_k": 60,
        "item_scores": item_scores,
    }


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
        scored = _with_fusion_metadata(item, learned_score, components)
        evidence_id = str(scored.get("evidence_id") or f"item-{index}")
        item_scores[evidence_id] = learned_score
        scored_items.append((learned_score, index, scored))

    scored_items.sort(key=lambda row: (-row[0], row[1]))
    return [item for _, _, item in scored_items], {
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
) -> dict[str, Any]:
    scored = dict(item)
    metadata = dict(scored.get("metadata") or {})
    metadata["hybrid_fusion_score"] = score
    metadata["hybrid_fusion_components"] = components
    scored["metadata"] = metadata
    return scored


def _rrf_scores_by_item(
    weighted_rows: list[tuple[float, int, dict[str, Any], dict[str, float]]],
) -> dict[str, float]:
    scores: dict[str, float] = {}
    for _modality, rows in _rows_by_modality(weighted_rows).items():
        ranked = sorted(rows, key=lambda row: (-row[0], row[1]))
        for rank, (_score, index, item, _components) in enumerate(ranked, start=1):
            evidence_id = str(item.get("evidence_id") or f"item-{index}")
            scores[evidence_id] = scores.get(evidence_id, 0.0) + 1.0 / (60 + rank)
    return scores


def _rows_by_modality(
    weighted_rows: list[tuple[float, int, dict[str, Any], dict[str, float]]],
) -> dict[str, list[tuple[float, int, dict[str, Any], dict[str, float]]]]:
    rows: dict[str, list[tuple[float, int, dict[str, Any], dict[str, float]]]] = {}
    for row in weighted_rows:
        modality = str(row[2].get("modality") or "text").strip() or "text"
        rows.setdefault(modality, []).append(row)
    return rows


def _dict_rows_by_modality(
    rows: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row["group"]), []).append(row)
    return grouped


def _modality_group(item: dict[str, Any]) -> str:
    modality = str(item.get("modality") or "text").strip() or "text"
    if modality in {"text", "page_image", "graph"}:
        return modality
    return "element"


def _modality_preference_bias(query: str, group: str) -> float:
    query_tokens = _tokens(query)
    if group == "text":
        return 0.003
    if group == "page_image" and query_tokens & MODALITY_TERMS["page_image"]:
        return 0.002
    if group == "element" and any(
        query_tokens & MODALITY_TERMS.get(modality, set())
        for modality in ("table", "formula", "figure")
    ):
        return 0.001
    return 0.0


def _score_margin(rows: list[dict[str, Any]], row: dict[str, Any]) -> float:
    peers = [item for item in rows if item["group"] == row["group"]]
    scores = sorted((float(item["score"]) for item in peers), reverse=True)
    if not scores:
        return 0.0
    current = float(row["score"])
    better = [score for score in scores if score > current]
    return round((better[-1] - current) if better else 0.0, 4)


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
        "reranker_score",
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
