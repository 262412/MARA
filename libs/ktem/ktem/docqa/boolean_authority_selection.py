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


def _deduplicated_authorities(
    authorities: list[BooleanEvidenceAuthority],
) -> tuple[BooleanEvidenceAuthority, ...]:
    deduplicated = {
        (authority.evidence_id, authority.span_start, authority.span_end): authority
        for authority in authorities
    }
    strongest_by_evidence: dict[str, BooleanEvidenceAuthority] = {}
    for authority in deduplicated.values():
        current = strongest_by_evidence.get(authority.evidence_id)
        if current is None or (
            -_authority_rank(authority),
            len(authority.quote),
            authority.span_id,
        ) < (
            -_authority_rank(current),
            len(current.quote),
            current.span_id,
        ):
            strongest_by_evidence[authority.evidence_id] = authority
    return tuple(
        sorted(
            strongest_by_evidence.values(),
            key=lambda value: (
                -_authority_rank(value),
                len(value.quote),
                value.evidence_id,
                value.span_id,
            ),
        )
    )
