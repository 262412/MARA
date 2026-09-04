from __future__ import annotations

from typing import Any

from ktem.docqa.finance_gross_margin_profile import finance_gross_margin_profile_answer
from ktem.docqa.finance_narrative_answer import finance_narrative_answer
from ktem.docqa.finance_numeric_answer import finance_numeric_answer
from ktem.docqa.finance_segment_comparison import finance_segment_comparison_answer
from ktem.docqa.finance_typed_adequacy import (
    ensure_finance_numeric_trace as _ensure_finance_numeric_trace,
)
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
    gross_margin_profile = finance_gross_margin_profile_answer(
        request_planning_question(request),
        evidence_items,
    )
    if gross_margin_profile is not None:
        bundle.metadata["generation_backend"] = "finance_gross_margin_profile_answerer"
        bundle.metadata[
            "finance_gross_margin_profile_trace"
        ] = gross_margin_profile.as_trace()
        return gross_margin_profile.answer
    narrative = finance_narrative_answer(
        request_planning_question(request),
        evidence_items,
    )
    if narrative is not None:
        bundle.metadata["generation_backend"] = "finance_narrative_answerer"
        return narrative
    comparison = finance_segment_comparison_answer(
        request_planning_question(request),
        evidence_items,
        query_plan=dict(getattr(bundle, "metadata", {}).get("query_plan") or {}),
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
    _ensure_finance_numeric_trace(request, bundle)
