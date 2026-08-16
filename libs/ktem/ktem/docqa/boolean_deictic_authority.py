from __future__ import annotations

import re

from .boolean_authoritative_conflict import ambiguous_authority_claim
from .boolean_authority_schema import BooleanClaimAuthority, BooleanEvidenceAuthority

_DEICTIC_OBJECT_RE = re.compile(
    r"\b(?:this|that|these|those)\s+(?P<head>[a-z][a-z-]*)s?\b",
    re.IGNORECASE,
)
_GENERIC_OBJECT_LABELS = {
    "a",
    "an",
    "any",
    "current",
    "each",
    "new",
    "other",
    "our",
    "proposed",
    "same",
    "that",
    "the",
    "their",
    "these",
    "this",
    "those",
}


def ambiguous_deictic_object_authority(
    prompt: str,
    input_polarity: str,
    probe_polarity: str,
    authorities: tuple[BooleanEvidenceAuthority, ...],
) -> BooleanClaimAuthority | None:
    match = _DEICTIC_OBJECT_RE.search(str(prompt or ""))
    if match is None or len(authorities) < 2:
        return None
    head = match.group("head").casefold()
    bindings: dict[str, str] = {}
    for authority in authorities:
        label = _explicit_object_label(authority.quote, head)
        if not label:
            return None
        bindings[authority.evidence_ref] = label
    if len(set(bindings.values())) < 2:
        return None
    return ambiguous_authority_claim(
        prompt,
        input_polarity,
        probe_polarity,
        authorities,
        bindings,
    )


def _explicit_object_label(quote: str, head: str) -> str:
    matches = list(
        re.finditer(
            rf"\b(?P<label>[a-z][a-z0-9_-]*)\s+{re.escape(head)}s?\b",
            str(quote or ""),
            flags=re.IGNORECASE,
        )
    )
    if len(matches) != 1:
        return ""
    label = matches[0].group("label").casefold()
    return "" if label in _GENERIC_OBJECT_LABELS else label
