from __future__ import annotations

from typing import Any

from .metrics import normalize_text

_BACKEND_FIELDS = {
    "text_retriever": ("text_retriever_backend", "retrieval_backend"),
    "visual_retriever": ("visual_retriever_backend",),
    "visual_backend_type": ("visual_backend_type",),
    "graph_backend": ("graph_backend",),
    "planner_backend": ("planner_backend", "planner_model"),
    "generator_backend": ("generator_backend", "llm_name"),
}


def research_adapter_metrics(prediction: dict[str, Any]) -> dict[str, dict[str, Any]]:
    metrics = dict(prediction.get("metrics") or {})
    return {
        "alce": _alce_metrics(prediction, metrics),
        "mmdocrag": _mmdocrag_metrics(metrics),
        "ragtruth": _ragtruth_metrics(prediction, metrics),
    }


def route_backend_metadata(
    route: dict[str, Any],
    config: Any,
) -> dict[str, str]:
    metadata = {
        output_key: _backend_value(route, config, candidates, output_key)
        for output_key, candidates in _BACKEND_FIELDS.items()
    }
    graph_mode = _backend_value(route, config, ("graph_mode",), "graph_mode")
    if graph_mode:
        metadata["graph_mode"] = graph_mode
    return metadata


def _alce_metrics(
    prediction: dict[str, Any],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    unsupported_rate = float(metrics.get("unsupported_claim_rate") or 0.0)
    return {
        "fluency": _fluency_score(str(prediction.get("predicted_answer") or "")),
        "correctness": _correctness_score(prediction, metrics),
        "citation_recall": metrics.get("citation_recall"),
        "citation_precision": metrics.get("citation_precision"),
        "attributable_claim_rate": max(0.0, 1.0 - unsupported_rate),
        "citation_quality": metrics.get("citation_recall"),
    }


def _mmdocrag_metrics(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "image_quote_hit": metrics.get("image_quote_hit"),
        "multimodal_answer_support": metrics.get("multimodal_answer_support"),
        "cross_page_evidence_hit": metrics.get("cross_page_evidence_hit"),
        "hard_negative_rejection": metrics.get("hard_negative_rejection"),
        "page_hit": metrics.get("page_hit"),
        "element_hit": metrics.get("element_hit"),
    }


def _ragtruth_metrics(
    prediction: dict[str, Any],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    verify_decision = dict(prediction.get("verify_decision") or {})
    contradictions = verify_decision.get("contradictions") or []
    return {
        "unsupported_claim_count": metrics.get("unsupported_claim_count"),
        "unsupported_claim_rate": metrics.get("unsupported_claim_rate"),
        "contradiction_count": float(len(contradictions)),
        "abstention_correctness": metrics.get("abstention_correctness"),
        "claim_hallucination_rate": metrics.get("unsupported_claim_rate"),
        "unsupported_span_count": metrics.get("unsupported_claim_count"),
    }


def _fluency_score(answer: str) -> float:
    return float(bool(normalize_text(answer)))


def _correctness_score(
    prediction: dict[str, Any],
    metrics: dict[str, Any],
) -> float:
    normalized_answer = normalize_text(str(prediction.get("predicted_answer") or ""))
    gold_answers = [
        normalize_text(str(item or ""))
        for item in prediction.get("gold_answers", [])
        if str(item or "").strip()
    ]
    if any(gold and gold in normalized_answer for gold in gold_answers):
        return 1.0
    return float(metrics.get("f1") or 0.0)


def _backend_value(
    route: dict[str, Any],
    config: Any,
    candidates: tuple[str, ...],
    output_key: str,
) -> str:
    for key in candidates:
        value = route.get(key)
        if value:
            return str(value)
        value = getattr(config, key, None)
        if value:
            return str(value)
    if output_key == "text_retriever":
        return str(getattr(config, "retrieval_mode", "") or "")
    if output_key == "generator_backend":
        return str(getattr(config, "engine", "") or "")
    return ""
