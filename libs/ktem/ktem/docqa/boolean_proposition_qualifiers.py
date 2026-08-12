from __future__ import annotations

import re


def proposition_qualifier(value: str) -> str:
    """Return the normalized magnitude or significance qualifier."""

    lowered = str(value or "").lower()
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
        ("marginal", r"\bmarginal(?:ly)?\b"),
        ("small", r"\bsmall(?:er|est)?\b"),
        ("minor", r"\bminor\b"),
    )
    for name, pattern in markers:
        if re.search(pattern, lowered, flags=re.IGNORECASE):
            return name
    return "none"
