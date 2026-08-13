from __future__ import annotations

import re

from .boolean_proposition_conditions import (
    without_condition_targets_question,
    without_target_has_negative_outcome,
)


def proposition_qualifier(value: str, *, question: str = "") -> str:
    """Return the normalized magnitude or significance qualifier."""

    lowered = str(value or "").lower()
    if question and without_target_has_negative_outcome(question, lowered):
        return "required_condition"
    markers = (
        (
            "not_required",
            r"\b(?:without|unnecessary|optional|not\s+needed|not\s+required|"
            r"does\s+not\s+require|do\s+not\s+require|did\s+not\s+require|"
            r"isn't\s+needed|is\s+not\s+needed)\b",
        ),
        (
            "non_significant",
            r"\b(?:non[- ]?significant|insignificant|not\s+significant)\b",
        ),
        (
            "limited_information",
            r"\b(?:little|minimal|negligible|almost\s+no|no)\s+"
            r"(?:useful\s+)?(?:information|evidence|benefit|gain|impact)\b",
        ),
        ("marginal", r"\bmarginal(?:ly)?\b"),
        ("small", r"\bsmall(?:er|est)?\b"),
        ("minor", r"\bminor\b"),
    )
    for name, pattern in markers:
        if not re.search(pattern, lowered, flags=re.IGNORECASE):
            continue
        if (
            name == "not_required"
            and question
            and "without" in lowered
            and not without_condition_targets_question(question, lowered)
        ):
            continue
        return name
    return "none"
