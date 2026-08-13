from __future__ import annotations

import re

from .boolean_authority_schema import BooleanEvidenceAuthority


def _best_authority(
    values: tuple[BooleanEvidenceAuthority, ...],
) -> BooleanEvidenceAuthority:
    return min(
        values,
        key=lambda value: (
            -_authority_rank(value),
            len(value.quote),
            value.evidence_id,
            value.span_id,
        ),
    )


def _authority_rank(value: BooleanEvidenceAuthority) -> int:
    lowered = value.quote.lower()
    if any(
        marker in lowered
        for marker in ("non-significant", "non significant", "insignificant")
    ):
        return 4
    if re.search(
        r"\b(?:little|minimal|negligible|almost\s+no|no)\s+"
        r"(?:useful\s+)?(?:information|evidence|benefit|gain|impact)\b",
        lowered,
    ):
        return 3
    if any(marker in lowered for marker in ("small", "marginal", "minor")):
        return 2
    return int("only" in lowered)
