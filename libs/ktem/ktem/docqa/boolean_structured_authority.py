from __future__ import annotations

import re
from typing import Any

from . import boolean_evidence_scope as scope_evidence
from .boolean_authority_schema import BooleanEvidenceAuthority
from .boolean_proposition_compatibility import _object_compatibility
from .boolean_proposition_context import exact_proposition_context
from .boolean_proposition_qualifiers import proposition_qualifier
from .boolean_relations import primary_boolean_relation
from .evidence_identity import identity_of
from .query_phrase_extraction import (
    semantic_boolean_proposition_question,
    source_page_locator,
)


def structured_boolean_authorities(
    question: str,
    evidence_items: list[dict[str, Any]],
) -> tuple[BooleanEvidenceAuthority, ...]:
    """Return exact typed authorities produced by the shared scope resolver."""

    authorities = [
        authority
        for item in evidence_items
        if (authority := structured_boolean_authority(question, item)) is not None
    ]
    return tuple(
        sorted(
            {
                (authority.evidence_id, authority.evidence_ref): authority
                for authority in authorities
            }.values(),
            key=lambda value: (
                value.polarity,
                len(value.quote),
                value.evidence_id,
                value.evidence_ref,
            ),
        )
    )


def structured_boolean_authority(
    question: str,
    item: dict[str, Any],
) -> BooleanEvidenceAuthority | None:
    """Resolve one candidate into the same exact authority used by verification."""

    if _title_or_heading_item(item):
        return None
    resolution = scope_evidence.resolve_closed_scope_boolean(question, [item])
    if resolution is None or resolution.polarity not in {"yes", "no"}:
        return None
    try:
        evidence_id = identity_of(item).key
        resolved_id = identity_of(resolution.evidence_item).key
    except ValueError:
        return None
    quote = str(resolution.evidence_quote or "")
    text = scope_evidence.evidence_item_text(item)
    if evidence_id != resolved_id or not quote or quote not in text:
        return None
    decision = resolution.decision
    if not (
        decision.scope_valid
        and decision.actor == "current_paper"
        and decision.section_role not in {"related_work", "future_work"}
    ):
        return None
    window = exact_proposition_context(
        text,
        quote,
        canonical_start=_optional_int(item.get("canonical_start")),
    )
    if window is None or window.text != quote:
        return None
    semantic_question = semantic_boolean_proposition_question(question)
    relation = primary_boolean_relation(semantic_question) or _structured_relation(
        decision.reason
    )
    _object_score, proposition_object = _object_compatibility(
        semantic_question,
        quote,
    )
    if not relation or not proposition_object:
        return None
    source_id, page_label = source_page_locator(item)
    span_start = (
        window.canonical_start if window.canonical_start is not None else window.start
    )
    span_end = window.canonical_end if window.canonical_end is not None else window.end
    evidence_ref = f"{evidence_id}#quote:{span_start}:{span_end}"
    return BooleanEvidenceAuthority(
        evidence_id=evidence_id,
        evidence_ref=evidence_ref,
        span_id=evidence_ref,
        quote=window.text,
        span_start=window.start,
        span_end=window.end,
        canonical_start=window.canonical_start,
        canonical_end=window.canonical_end,
        actor=decision.actor,
        section_scope=(
            "document" if decision.section_role == "unknown" else decision.section_role
        ),
        relation=relation,
        object=proposition_object,
        quantifier=decision.quantifier or "none",
        polarity=resolution.polarity,
        reason=decision.reason,
        qualifier=proposition_qualifier(window.text, question=semantic_question),
        source_id=source_id,
        page_label=page_label,
    )


def _title_or_heading_item(item: dict[str, Any]) -> bool:
    kind = " ".join(
        str(item.get(key) or "").lower()
        for key in ("element_type", "modality", "section_id", "section_title")
    )
    return bool(re.search(r"\btitle\b|\bheading\b", kind))


def _structured_relation(reason: str) -> str:
    return "mention" if reason == "explicit_target_downside" else ""


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
