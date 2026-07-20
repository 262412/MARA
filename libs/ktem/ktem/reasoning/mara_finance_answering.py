from __future__ import annotations

from typing import Any

from ktem.docqa.finance_numeric_answer import finance_numeric_answer


def route_finance_numeric_answer(
    request: Any, decision: Any, bundle: Any
) -> str | None:
    if str(getattr(decision, "route", "") or "") not in {"text_rag", "hybrid_rag"}:
        return None
    domain = str(getattr(request, "verification_domain", "") or "").strip().lower()
    if domain not in {"finance", "financial", "financebench"}:
        return None
    result = finance_numeric_answer(
        str(getattr(request, "prompt", "") or ""),
        [item for item in getattr(bundle, "items", []) or [] if isinstance(item, dict)],
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
