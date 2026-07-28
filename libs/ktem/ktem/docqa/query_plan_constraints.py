from __future__ import annotations

from typing import Any

from .finance_query_planning import finance_comparison_excluded_entities


def query_plan_constraints(
    question: str,
    *,
    question_type: str,
    periods: list[str],
    verification_domain: str,
    segment_comparison: bool,
    capabilities: dict[str, Any] | None = None,
) -> dict[str, Any]:
    capabilities = dict(capabilities or {})
    cross_page = bool(
        capabilities.get("requires_multiple_evidence") or question_type == "cross_page"
    )
    lowered_question = str(question or "").lower()
    constraints: dict[str, Any] = {
        "periods": periods,
        "verification_domain": str(verification_domain or ""),
        **capabilities,
        "requires_distinct_evidence": cross_page,
        "requires_distinct_source_pages": bool(
            capabilities.get("requires_distinct_source_pages")
            or (
                cross_page
                and ("page" in lowered_question or "across" in lowered_question)
            )
        ),
        "requires_structure": (
            question_type in {"cross_page", "multi_period_numeric", "comparison_argmax"}
            or (
                "finance" in str(verification_domain or "").lower()
                and question_type == "numeric"
            )
        ),
    }
    if segment_comparison:
        constraints.update(
            {
                "comparison_operator": "proportional_increase",
                "excluded_entities": finance_comparison_excluded_entities(question),
            }
        )
    return constraints
