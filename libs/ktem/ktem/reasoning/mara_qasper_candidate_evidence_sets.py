from __future__ import annotations

from typing import Any

from ktem.docqa.canonical_proposition_evidence_plan import (
    canonical_proposition_evidence_selection,
    canonical_selector_sort_key,
)


def candidate_span_set(
    question: str,
    selectors: list[dict[str, Any]],
    required_slots: tuple[str, ...],
    *,
    polarity: str | None,
) -> tuple[dict[str, Any], ...] | None:
    """Select the best complete event-bound span set.

    ``polarity=None`` is retained for the private compatibility seam.  It now
    returns only a relation-bound plan; a structurally complete but unresolved
    slot union is never promoted to a normal binding.
    """

    selection = canonical_proposition_evidence_selection(
        question,
        selectors,
        required_slots,
    )
    if polarity == "yes":
        return selection.support
    if polarity == "no":
        return selection.contradiction
    return selection.support or selection.contradiction


def selector_sort_key(value: dict[str, Any]) -> tuple[str, int, int, str]:
    return canonical_selector_sort_key(value)
