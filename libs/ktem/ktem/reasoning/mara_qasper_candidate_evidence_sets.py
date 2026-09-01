"""Low-entropy QASPER selector compatibility helpers.

The canonical DocQA planner owns bounded combination enumeration and semantic
set validation.  This module keeps the older reasoning import path small while
enforcing the additional rule that an explicitly labelled predicate paraphrase
must carry a verifiable, local attestation before it can enter that planner.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from ktem.docqa.canonical_proposition_evidence_plan import (
    canonical_ranked_evidence_sets,
)
from ktem.docqa.canonical_proposition_evidence_plan_contract import (
    canonical_selector_sort_key,
)

from .mara_qasper_candidate_selector_semantics import (
    verified_selector_semantic_alignment as _verified_alignment,
)

_POLARITY_RELATIONS = {
    "yes": "proposition_support",
    "no": "explicit_contradiction",
}


def enumerate_candidate_span_sets(
    question: str,
    selectors: Sequence[dict[str, Any]],
    required_slots: Sequence[str],
    *,
    polarity: str | None,
) -> tuple[tuple[dict[str, Any], ...], ...]:
    """Return every shared-planner-valid set in deterministic semantic order.

    The selector mappings returned by the canonical planner are not rebuilt or
    normalised here.  Consequently exact local offsets, evidence identity, and
    event identity remain the values that were audited at the selector stage.
    """

    if polarity is not None and polarity not in _POLARITY_RELATIONS:
        return ()
    trusted = tuple(
        selector
        for selector in selectors
        if isinstance(selector, dict)
        and _explicit_paraphrase_is_audited(question, selector)
    )
    relations = (
        (_POLARITY_RELATIONS[polarity],)
        if polarity is not None
        else tuple(_POLARITY_RELATIONS.values())
    )
    alternatives: list[tuple[dict[str, Any], ...]] = []
    seen: set[tuple[tuple[str, str], ...]] = set()
    for relation in relations:
        for selected in canonical_ranked_evidence_sets(
            question,
            trusted,
            required_slots,
            polarity_relation=relation,
        ):
            identity = tuple(
                (
                    str(selector.get("evidence_id") or ""),
                    str(selector.get("selector_id") or ""),
                )
                for selector in selected
            )
            if identity in seen:
                continue
            seen.add(identity)
            alternatives.append(tuple(selected))
    return tuple(alternatives)


def candidate_span_set(
    question: str,
    selectors: list[dict[str, Any]],
    required_slots: tuple[str, ...],
    *,
    polarity: str | None,
) -> tuple[dict[str, Any], ...] | None:
    """Return the highest-ranked valid set, retaining the historical API."""

    alternatives = enumerate_candidate_span_sets(
        question,
        selectors,
        required_slots,
        polarity=polarity,
    )
    return alternatives[0] if alternatives else None


def selector_sort_key(value: dict[str, Any]) -> tuple[str, int, int, str]:
    return canonical_selector_sort_key(value)


def _explicit_paraphrase_is_audited(
    question: str,
    selector: Mapping[str, Any],
) -> bool:
    """Fail closed only for an explicit paraphrase claim.

    Existing exact/alias selectors continue through the canonical lexical
    checks.  A selector that calls itself a paraphrase must bind its own exact
    span, event, proposition digest, slot references, object coverage, and
    attestation digest; no dataset answer, example ID, or spelling alias is
    consulted.
    """

    if str(selector.get("predicate_match_kind") or "").strip() != "paraphrase":
        return True
    return _verified_alignment(question, selector) is not None
