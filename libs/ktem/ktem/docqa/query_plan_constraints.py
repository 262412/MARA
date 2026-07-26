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
) -> dict[str, Any]:
    constraints: dict[str, Any] = {
        "periods": periods,
        "verification_domain": str(verification_domain or ""),
        "requires_structure": question_type
        in {"cross_page", "multi_period_numeric", "comparison_argmax"},
    }
    if segment_comparison:
        constraints.update(
            {
                "comparison_operator": "proportional_increase",
                "excluded_entities": finance_comparison_excluded_entities(question),
            }
        )
    return constraints
