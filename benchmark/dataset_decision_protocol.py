from __future__ import annotations

from collections import OrderedDict
from typing import Any

from .metrics import normalize_text

PHASE2_PROMPT_POLICY = "gold_answer_v1"

_DATASET_DECISIONS: tuple[dict[str, Any], ...] = (
    {
        "dataset_key": "financebench",
        "family": "text_financial_qa",
        "decision": "diagnostic_followup",
        "headline_routes": ["text_rag"],
        "diagnostic_routes": ["hybrid_rag"],
        "blocked_routes": ["controller_auto", "crag_guarded"],
        "blockers": [
            "retrieval_evidence_adequacy",
            "numeric_reasoning",
            "controller_guarded_timeout",
        ],
        "score_authority": "local_dataset_native",
        "rationale": (
            "Gold and matched baseline small samples both show false "
            "abstention and numeric-answer mismatch; keep as diagnostic until "
            "retrieval and numeric evidence selection improve."
        ),
    },
    {
        "dataset_key": "qasper",
        "family": "text_scientific_qa",
        "decision": "main_quality_candidate",
        "headline_routes": ["text_rag"],
        "diagnostic_routes": ["controller_auto", "crag_guarded"],
        "blocked_routes": [],
        "blockers": [],
        "score_authority": "local_dataset_native",
        "rationale": (
            "Text route is runnable under gold and matched baseline prompts "
            "with non-zero exact/F1 signal."
        ),
    },
    {
        "dataset_key": "ragtruth",
        "family": "hallucination_guardrail",
        "decision": "main_guardrail_candidate",
        "headline_routes": ["crag_guarded"],
        "diagnostic_routes": ["text_rag"],
        "blocked_routes": [],
        "blockers": ["paper_grade_evaluator_unavailable"],
        "score_authority": "local_dataset_native",
        "rationale": (
            "Gold-answer prompt improved the matched small-sample native score, "
            "but paper-grade evaluator remains unavailable."
        ),
    },
    {
        "dataset_key": "alce",
        "family": "citation_grounded_qa",
        "decision": "secondary_citation_candidate",
        "headline_routes": ["text_rag"],
        "diagnostic_routes": ["crag_guarded"],
        "blocked_routes": [],
        "blockers": ["paper_grade_evaluator_unavailable"],
        "score_authority": "local_dataset_native",
        "rationale": (
            "Local adapted score is stable in small samples; keep as secondary "
            "citation-heavy candidate until external evaluator is configured."
        ),
    },
    {
        "dataset_key": "mmdocrag",
        "family": "multimodal_document_qa",
        "decision": "provisional_multimodal_candidate",
        "headline_routes": ["text_rag"],
        "diagnostic_routes": ["page_image_rag_vlm", "hybrid_rag"],
        "blocked_routes": ["page_image_rag_vlm"],
        "blockers": ["requires_vlm_backend"],
        "score_authority": "local_dataset_native",
        "rationale": (
            "Text route is runnable; VLM route remains blocked by 8001 backend "
            "memory pressure."
        ),
    },
    {
        "dataset_key": "slidevqa",
        "family": "slide_visual_qa",
        "decision": "blocked_visual_candidate",
        "headline_routes": [],
        "diagnostic_routes": ["text_rag", "page_image_rag_vlm"],
        "blocked_routes": ["page_image_rag_vlm"],
        "blockers": ["requires_vlm_backend", "text_route_no_visual_evidence"],
        "score_authority": "local_dataset_native",
        "rationale": (
            "Text route returns no retrieved evidence in matched small samples; "
            "visual route requires a live VLM backend."
        ),
    },
    {
        "dataset_key": "vidore",
        "family": "visual_retrieval",
        "decision": "retrieval_diagnostic",
        "headline_routes": [],
        "diagnostic_routes": ["colqwen_retriever_only", "colpali_retriever_only"],
        "blocked_routes": ["page_image_rag_vlm"],
        "blockers": ["missing_full_qa_generation_route", "requires_vlm_backend"],
        "score_authority": "retrieval_diagnostic_proxy",
        "rationale": (
            "Current manifest routes are retriever-only diagnostics; full QA "
            "needs a VLM generation route."
        ),
    },
)


def phase2_dataset_decision(dataset_name: str) -> dict[str, Any]:
    normalized = _normalize_key(dataset_name)
    for decision in _DATASET_DECISIONS:
        if decision["dataset_key"] in normalized:
            return _decision_payload(decision)
    return _decision_payload(
        {
            "dataset_key": "unknown",
            "family": "unknown",
            "decision": "unclassified",
            "headline_routes": [],
            "diagnostic_routes": [],
            "blocked_routes": [],
            "blockers": ["not_in_phase2_matrix"],
            "score_authority": "unknown",
            "rationale": "Dataset is not part of the Phase 2 thesis matrix.",
        }
    )


def phase2_failure_type(prediction: dict[str, Any]) -> str:
    if str(prediction.get("error_type") or "").strip() == "route_timeout":
        return "route_timeout"
    if str(prediction.get("error") or "").strip():
        return "execution_error"
    if _is_retriever_only_without_generation(prediction):
        return "retrieval_diagnostic_no_generation"

    metrics = dict(prediction.get("metrics") or {})
    diagnostics = dict(prediction.get("diagnostics") or {})
    if metrics.get("false_abstention") == 1.0:
        retrieved_count = diagnostics.get("retrieved_count")
        if retrieved_count is None:
            retrieved_count = len(prediction.get("retrieved_hits") or [])
        if int(retrieved_count or 0) == 0:
            return "false_abstention_no_evidence"
        return "false_abstention_after_retrieval"

    failure_class = str(diagnostics.get("failure_class") or "").strip()
    if failure_class and failure_class != "none":
        return failure_class

    f1 = metrics.get("f1")
    if isinstance(f1, (int, float)) and float(f1) == 0.0:
        if int(
            diagnostics.get("retrieved_count")
            or len(prediction.get("retrieved_hits") or [])
        ):
            return "answer_mismatch_after_retrieval"
        return "answer_mismatch_no_retrieval"
    if _answer_mismatches_gold(prediction):
        if int(
            diagnostics.get("retrieved_count")
            or len(prediction.get("retrieved_hits") or [])
        ):
            return "answer_mismatch_after_retrieval"
        return "answer_mismatch_no_retrieval"

    return "none"


def phase2_failure_counts(
    dataset_name: str,
    predictions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    decision = phase2_dataset_decision(dataset_name)
    counts: OrderedDict[tuple[str, str], int] = OrderedDict()
    for prediction in predictions:
        route = str(prediction.get("route") or "").strip()
        failure_type = phase2_failure_type(prediction)
        key = (route, failure_type)
        counts[key] = counts.get(key, 0) + 1
    return [
        {
            "dataset_name": dataset_name,
            "dataset_decision": decision["decision"],
            "route": route,
            "phase2_failure_type": failure_type,
            "count": count,
        }
        for (route, failure_type), count in counts.items()
    ]


def _decision_payload(decision: dict[str, Any]) -> dict[str, Any]:
    return {
        **decision,
        "benchmark_prompt_policy": PHASE2_PROMPT_POLICY,
        "benchmark_no_think": True,
    }


def _is_retriever_only_without_generation(prediction: dict[str, Any]) -> bool:
    route = str(prediction.get("route") or "").strip().lower()
    if route.endswith("_retriever_only"):
        return True
    answer = normalize_text(str(prediction.get("predicted_answer") or ""))
    return "no vlm backend is configured" in answer


def _answer_mismatches_gold(prediction: dict[str, Any]) -> bool:
    predicted = normalize_text(
        str(
            prediction.get("answer_for_scoring")
            or prediction.get("predicted_answer")
            or ""
        )
    )
    if not predicted:
        return False
    gold_answers = [
        normalize_text(str(answer))
        for answer in prediction.get("gold_answers") or []
        if normalize_text(str(answer))
    ]
    return bool(gold_answers) and predicted not in set(gold_answers)


def _normalize_key(value: str) -> str:
    return str(value or "").strip().lower().replace("-", "_")
