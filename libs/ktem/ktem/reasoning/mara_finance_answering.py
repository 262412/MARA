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
    if result is None or result.confidence < 0.70:
        if result is not None:
            bundle.metadata["finance_numeric_trace"] = result.as_trace()
        return None
    bundle.metadata["generation_backend"] = "finance_numeric_answerer"
    bundle.metadata["finance_numeric_trace"] = result.as_trace()
    return result.answer
