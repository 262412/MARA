from __future__ import annotations

import re
from typing import Any

from .retrieval_adequacy import financial_statement_match_count

FUSION_RANKER = "weighted_cross_modal_v1"
RRF_RANKER = "reciprocal_rank_fusion_v1"
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
    if str(strategy or "").strip().lower() == "rrf":
        return _fuse_with_rrf(query, items, domain=domain)
    return _fuse_with_weighted_scores(query, items, domain=domain)


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
        "ranker": FUSION_RANKER,
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
