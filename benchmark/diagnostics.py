from __future__ import annotations

from collections import OrderedDict
from typing import Any

from ktem.docqa.evidence_text import extract_final_answer_text

from .citation_metrics import citation_recall_score
from .metrics import normalize_text, page_hit_score, round_metric, safe_mean
from .page_alignment import evidence_aligned_page_hit_score

DIAGNOSTIC_AVERAGE_KEYS = (
    "retrieved_count",
    "evidence_item_count",
    "gold_document_hit",
    "gold_page_hit",
    "gold_span_hit",
    "answer_nonempty_after_cleaning",
)


def prediction_diagnostics(prediction: dict[str, Any]) -> dict[str, Any]:
    retrieved_hits = _records(prediction.get("retrieved_hits"))
    evidence_items = _evidence_items(prediction)
    gold_evidence = _records(prediction.get("gold_evidence"))
    recommended_routes = recommended_routes_for_prediction(prediction)
    selected_route = _selected_controller_route(prediction)
    cleaned_answer = extract_final_answer_text(
        str(prediction.get("predicted_answer") or "")
    )
    gold_document_hit = _gold_document_hit(gold_evidence, retrieved_hits)
    gold_page_hit = _gold_page_hit(prediction, gold_evidence)
    gold_span_hit = _gold_span_hit(gold_evidence, retrieved_hits, evidence_items)
    retrieval_failure_type = _retrieval_failure_type(
        prediction,
        retrieved_hits,
        gold_document_hit,
        gold_page_hit,
        gold_span_hit,
    )
    citation_failure_type = _citation_failure_type(prediction, gold_evidence)
    return {
        "retrieved_count": len(retrieved_hits),
        "evidence_item_count": len(evidence_items),
        "gold_document_hit": gold_document_hit,
        "gold_page_hit": gold_page_hit,
        "gold_span_hit": gold_span_hit,
        "retrieval_failure_type": retrieval_failure_type,
        "citation_failure_type": citation_failure_type,
        "failure_class": _failure_class(
            retrieval_failure_type,
            citation_failure_type,
        ),
        "answer_nonempty_after_cleaning": float(bool(normalize_text(cleaned_answer))),
        "verifier_status": str(
            (prediction.get("verify_decision") or {}).get("status") or ""
        ),
        "guardrail_action": str(
            (prediction.get("guardrail_decision") or {}).get("action") or ""
        ),
        "controller_selected_route": selected_route,
        "recommended_routes": recommended_routes,
        "controller_route_match": float(selected_route in recommended_routes)
        if selected_route and recommended_routes
        else None,
    }


def recommended_routes_for_prediction(prediction: dict[str, Any]) -> list[str]:
    answer_type = str(prediction.get("answer_type") or "").strip().lower()
    scope = str(prediction.get("scope") or "").strip().lower()
    modality = str(prediction.get("modality") or "").strip().lower()
    question = str(prediction.get("question") or "").strip().lower()
    gold_evidence = _records(prediction.get("gold_evidence"))

    if answer_type == "verification" or (
        prediction.get("expected_guardrails") or {}
    ).get("unsupported_claims_expected"):
        return ["doc_text", "hybrid"]
    if scope == "multi_document" or answer_type in {"summary", "compare"}:
        return ["graph_global", "hybrid", "doc_text"]
    if any(term in question for term in ("compare", "summarize", "across sources")):
        return ["graph_global", "hybrid", "doc_text"]
    if _requires_visual_or_element_route(modality, gold_evidence):
        return ["hybrid", "doc_page_image", "doc_element"]
    return ["doc_text", "hybrid"]


def dataset_route_diagnostics(
    dataset_name: str,
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for route in _ordered_values(predictions, "route"):
        route_predictions = [
            prediction
            for prediction in predictions
            if str(prediction.get("route") or "") == route
        ]
        row: dict[str, Any] = {
            "dataset_name": dataset_name,
            "route": route,
            "num_predictions": len(route_predictions),
        }
        for key in DIAGNOSTIC_AVERAGE_KEYS:
            row[f"avg_{key}"] = round_metric(
                safe_mean(
                    [
                        (prediction.get("diagnostics") or {}).get(key)
                        for prediction in route_predictions
                    ]
                )
            )
        rows.append(row)
    return rows


def diagnostic_failure_counts(
    dataset_name: str,
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    counts: OrderedDict[tuple[str, str, str, str], int] = OrderedDict()
    for prediction in predictions:
        route = str(prediction.get("route") or "").strip()
        diagnostics = prediction.get("diagnostics") or {}
        failure_class = str(diagnostics.get("failure_class") or "unknown")
        retrieval_failure = str(diagnostics.get("retrieval_failure_type") or "unknown")
        citation_failure = str(diagnostics.get("citation_failure_type") or "unknown")
        key = (route, failure_class, retrieval_failure, citation_failure)
        counts[key] = counts.get(key, 0) + 1
    return [
        {
            "dataset_name": dataset_name,
            "route": route,
            "failure_class": failure_class,
            "retrieval_failure_type": retrieval_failure,
            "citation_failure_type": citation_failure,
            "count": count,
        }
        for (
            route,
            failure_class,
            retrieval_failure,
            citation_failure,
        ), count in counts.items()
    ]


def route_confusion_table(
    dataset_name: str,
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    counts: OrderedDict[tuple[str, str, str], int] = OrderedDict()
    for prediction in predictions:
        route = str(prediction.get("route") or "").strip()
        diagnostics = prediction.get("diagnostics") or {}
        recommended_routes = list(diagnostics.get("recommended_routes") or [])
        recommended_route = str(recommended_routes[0] if recommended_routes else "")
        selected_route = str(diagnostics.get("controller_selected_route") or "")
        key = (route, recommended_route, selected_route)
        counts[key] = counts.get(key, 0) + 1
    return [
        {
            "dataset_name": dataset_name,
            "route": route,
            "recommended_route": recommended_route,
            "selected_route": selected_route,
            "count": count,
        }
        for (route, recommended_route, selected_route), count in counts.items()
    ]


def _records(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value or [] if isinstance(item, dict)]


def _evidence_items(prediction: dict[str, Any]) -> list[dict[str, Any]]:
    evidence_bundle = prediction.get("evidence_bundle")
    if isinstance(evidence_bundle, dict):
        items = _records(evidence_bundle.get("items"))
        if items:
            return items
    evidence_metadata = prediction.get("evidence_metadata")
    if isinstance(evidence_metadata, dict):
        return _records(evidence_metadata.get("evidence"))
    return []


def _gold_document_hit(
    gold_evidence: list[dict[str, Any]],
    retrieved_hits: list[dict[str, Any]],
) -> float | None:
    gold_documents = {
        str(item.get("document_id") or item.get("source_id") or "").strip()
        for item in gold_evidence
        if str(item.get("document_id") or item.get("source_id") or "").strip()
    }
    if not gold_documents:
        return None
    retrieved_documents = {
        str(item.get("document_id") or item.get("source_id") or "").strip()
        for item in retrieved_hits
        if str(item.get("document_id") or item.get("source_id") or "").strip()
    }
    return float(bool(gold_documents & retrieved_documents))


def _gold_page_hit(
    prediction: dict[str, Any],
    gold_evidence: list[dict[str, Any]],
) -> float | None:
    gold_pages = {
        _page_key(
            item.get("page") if item.get("page") is not None else item.get("page_label")
        )
        for item in gold_evidence
    }
    gold_pages.update(_page_key(page) for page in prediction.get("gold_pages") or [])
    gold_pages.discard("")
    if not gold_pages:
        return None
    predicted_pages = {
        _page_key(page) for page in prediction.get("predicted_pages") or []
    }
    exact_score = page_hit_score(list(predicted_pages), list(gold_pages))
    if exact_score != 0.0:
        return exact_score
    return evidence_aligned_page_hit_score(
        list(predicted_pages),
        list(gold_pages),
        gold_evidence=gold_evidence,
        evidence_bundle=dict(prediction.get("evidence_bundle") or {}),
        retrieved_hits=_records(prediction.get("retrieved_hits")),
    )


def _gold_span_hit(
    gold_evidence: list[dict[str, Any]],
    retrieved_hits: list[dict[str, Any]],
    evidence_items: list[dict[str, Any]],
) -> float | None:
    spans = [
        normalize_text(str(item.get("span") or item.get("text") or ""))
        for item in gold_evidence
        if str(item.get("span") or item.get("text") or "").strip()
    ]
    if not spans:
        return None
    retrieved_text = normalize_text(
        " ".join(
            str(item.get(key) or "")
            for item in [*retrieved_hits, *evidence_items]
            for key in ("text", "snippet", "caption", "ocr_text", "vlm_text")
        )
    )
    return float(any(span and span in retrieved_text for span in spans))


def _retrieval_failure_type(
    prediction: dict[str, Any],
    retrieved_hits: list[dict[str, Any]],
    gold_document_hit: float | None,
    gold_page_hit: float | None,
    gold_span_hit: float | None,
) -> str:
    if _has_route_timeout(prediction):
        return "route_timeout"
    if _has_execution_error(prediction):
        return "execution_error"
    if not retrieved_hits:
        if _raw_retriever_zero(prediction):
            return "raw_retriever_zero"
        return "no_retrieved_hits"
    if gold_document_hit == 0.0:
        return "wrong_source"
    if gold_page_hit == 0.0:
        if prediction.get("predicted_pages"):
            return "wrong_page"
        return "missing_page_metadata"
    if gold_span_hit == 0.0:
        return "gold_span_missing"
    return "none"


def _citation_failure_type(
    prediction: dict[str, Any],
    gold_evidence: list[dict[str, Any]],
) -> str:
    if _has_route_timeout(prediction):
        return "not_evaluated_route_timeout"
    if _has_execution_error(prediction):
        return "not_evaluated_execution_error"
    gold_sources = {
        str(item).strip()
        for item in prediction.get("gold_sources") or []
        if str(item).strip()
    }
    gold_sources.update(
        str(item.get(key) or "").strip()
        for item in gold_evidence
        for key in ("source", "citation")
        if str(item.get(key) or "").strip()
    )
    if not gold_sources:
        return "none"

    predicted_sources = {
        str(item).strip()
        for item in prediction.get("predicted_sources") or []
        if str(item).strip()
    }
    if not predicted_sources:
        return "missing_citation_metadata"
    recall = citation_recall_score(
        list(predicted_sources),
        gold_evidence,
        evidence_bundle=dict(prediction.get("evidence_bundle") or {}),
        retrieved_hits=_records(prediction.get("retrieved_hits")),
    )
    if recall and recall > 0:
        return "none"
    if gold_sources.isdisjoint(predicted_sources):
        return "citation_miss"
    return "none"


def _failure_class(retrieval_failure_type: str, citation_failure_type: str) -> str:
    if retrieval_failure_type == "route_timeout":
        return "route_timeout"
    if retrieval_failure_type == "execution_error":
        return "execution_error"
    if retrieval_failure_type in {"raw_retriever_zero", "no_retrieved_hits"}:
        return "no_retrieved_hits"
    if retrieval_failure_type == "wrong_source":
        return "wrong_source"
    if retrieval_failure_type == "missing_page_metadata":
        return "missing_locator_metadata"
    if retrieval_failure_type == "wrong_page":
        return "wrong_locator"
    if retrieval_failure_type == "gold_span_missing":
        return "gold_span_missing"
    if citation_failure_type == "not_evaluated_execution_error":
        return "execution_error"
    if citation_failure_type == "not_evaluated_route_timeout":
        return "route_timeout"
    if citation_failure_type in {"citation_miss", "missing_citation_metadata"}:
        return "citation_miss"
    return "none"


def _has_execution_error(prediction: dict[str, Any]) -> bool:
    return bool(str(prediction.get("error") or "").strip())


def _has_route_timeout(prediction: dict[str, Any]) -> bool:
    return str(prediction.get("error_type") or "").strip() == "route_timeout"


def _raw_retriever_zero(prediction: dict[str, Any]) -> bool:
    counts: list[int] = []
    for row in _records(prediction.get("retrieval_trace")):
        stage = str(row.get("stage") or row.get("event") or row.get("name") or "")
        if "raw" not in stage and "retriever" not in stage:
            continue
        for key in ("count", "retrieved_count", "evidence_count", "result_count"):
            if key in row:
                counts.append(int(row.get(key) or 0))
                break
    return bool(counts) and max(counts) == 0


def _selected_controller_route(prediction: dict[str, Any]) -> str:
    route_decision = prediction.get("route_decision")
    if isinstance(route_decision, dict):
        route = str(route_decision.get("route") or "").strip()
        if route:
            return route
    controller_decision = prediction.get("controller_decision")
    if isinstance(controller_decision, dict):
        route = str(
            controller_decision.get("legacy_route")
            or controller_decision.get("route")
            or ""
        ).strip()
        if route:
            return route
    return str(prediction.get("route") or "").strip()


def _requires_visual_or_element_route(
    modality: str,
    gold_evidence: list[dict[str, Any]],
) -> bool:
    visual_modalities = {
        "figure",
        "formula",
        "image",
        "multimodal",
        "page_image",
        "slide",
        "table",
    }
    if modality in visual_modalities:
        return True
    for item in gold_evidence:
        item_modality = (
            str(item.get("modality") or item.get("element_type") or "").strip().lower()
        )
        if item.get("image_quote") or item_modality in visual_modalities:
            return True
    return False


def _ordered_values(predictions: list[dict[str, Any]], key: str) -> list[str]:
    values: list[str] = []
    for prediction in predictions:
        value = str(prediction.get(key) or "").strip()
        if value and value not in values:
            values.append(value)
    return values


def _page_key(value: Any) -> str:
    return str(value or "").strip()
