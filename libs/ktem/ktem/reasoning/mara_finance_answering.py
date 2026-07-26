from __future__ import annotations

from typing import Any

from ktem.docqa.finance_numeric_answer import finance_numeric_answer
from ktem.docqa.finance_segment_comparison import finance_segment_comparison_answer
from ktem.docqa.query_planning import request_planning_question


def route_finance_numeric_answer(
    request: Any, decision: Any, bundle: Any
) -> str | None:
    if str(getattr(decision, "route", "") or "") not in {"text_rag", "hybrid_rag"}:
        return None
    domain = str(getattr(request, "verification_domain", "") or "").strip().lower()
    if domain not in {"finance", "financial", "financebench"}:
        return None
    evidence_items = [
        item for item in getattr(bundle, "items", []) or [] if isinstance(item, dict)
    ]
    comparison = finance_segment_comparison_answer(
        request_planning_question(request),
        evidence_items,
    )
    if comparison is not None:
        bundle.metadata["finance_comparison_trace"] = comparison.as_trace()
        if comparison.status == "ok":
            bundle.metadata["generation_backend"] = "finance_comparison_answerer"
            return comparison.answer
        return None
    result = finance_numeric_answer(
        request_planning_question(request),
        evidence_items,
        query_plan=dict(getattr(bundle, "metadata", {}).get("query_plan") or {}),
    )
    if result is None:
        return None
    bundle.metadata["finance_numeric_trace"] = result.as_trace()
    verification = dict(result.calculation_verification or {})
    execution = dict(result.calculation_execution or {})
    if verification and (
        not verification.get("valid") or execution.get("status") != "ok"
    ):
        bundle.metadata[
            "generation_backend"
        ] = "finance_calculation_verification_failed"
        return ""
    if result.confidence < 0.70:
        return None
    bundle.metadata["generation_backend"] = "finance_numeric_answerer"
    return result.answer


def ensure_finance_numeric_trace(request: Any, bundle: Any) -> None:
    metadata = getattr(bundle, "metadata", None)
    if not isinstance(metadata, dict) or metadata.get("finance_numeric_trace"):
        return
    domain = str(getattr(request, "verification_domain", "") or "").strip().lower()
    if domain not in {"finance", "financial", "financebench"}:
        return
    evidence_items = [
        item for item in getattr(bundle, "items", []) or [] if isinstance(item, dict)
    ]
    comparison = finance_segment_comparison_answer(
        request_planning_question(request),
        evidence_items,
    )
    if comparison is not None:
        metadata["finance_comparison_trace"] = comparison.as_trace()
        return
    result = finance_numeric_answer(
        request_planning_question(request),
        evidence_items,
        query_plan=dict(metadata.get("query_plan") or {}),
    )
    if result is not None:
        metadata["finance_numeric_trace"] = result.as_trace()
