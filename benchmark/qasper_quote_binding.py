from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ktem.docqa.evidence_identity import identity_of

from .qasper_boolean_scope import evidence_item_text
from .qasper_evidence_identity import CanonicalQuoteSpan, canonical_quote_spans


@dataclass(frozen=True)
class _BoundQuote:
    evidence_id: str
    evidence_ref: str
    item: dict[str, Any]
    span: CanonicalQuoteSpan
    binding_status: str = "bound"


def evidence_ref_for_quote(
    quote: str,
    evidence_items: list[dict[str, Any]],
    alias_mapping: str,
) -> str:
    matches = []
    for entry in _alias_entries(alias_mapping):
        bound = _bound_quote_for_alias(entry, quote, evidence_items)
        if bound is not None:
            matches.append(bound.evidence_ref)
    return matches[0] if len(set(matches)) == 1 else ""


def bind_evidence_ref_to_quote(
    evidence_ref: str,
    quote: str,
    evidence_items: list[dict[str, Any]],
    alias_mapping: str,
) -> tuple[str, str]:
    bound, status = _bind_authoritative_quote(
        evidence_ref,
        quote,
        evidence_items,
        alias_mapping=alias_mapping,
        allow_ref_rebound=False,
    )
    if bound is None:
        return "", status
    resolved_ref = bound.evidence_ref or evidence_ref_for_quote(
        quote,
        evidence_items,
        alias_mapping,
    )
    return resolved_ref, status if resolved_ref else "evidence_ref_unresolved"


def resolve_evidence_ref_to_quote(
    evidence_ref: str,
    quote: str,
    evidence_items: list[dict[str, Any]],
    alias_mapping: str,
) -> tuple[str, str]:
    """Resolve an exact quote, allowing only a unique canonical ref rebound."""

    bound, status = _bind_authoritative_quote(
        evidence_ref,
        quote,
        evidence_items,
        alias_mapping=alias_mapping,
        allow_ref_rebound=True,
    )
    if bound is None:
        return "", status
    resolved_ref = bound.evidence_ref or evidence_ref_for_quote(
        quote,
        evidence_items,
        alias_mapping,
    )
    return resolved_ref, status if resolved_ref else "evidence_ref_unresolved"


def _bind_authoritative_quote(
    evidence_ref: str,
    quote: str,
    evidence_items: list[dict[str, Any]] | None,
    *,
    alias_mapping: str,
    allow_ref_rebound: bool = True,
) -> tuple[_BoundQuote | None, str]:
    if evidence_items is None:
        return None, "quote_identity_unresolved"
    normalized_quote = " ".join(str(quote or "").casefold().split())
    if not normalized_quote:
        return None, "quote_identity_unresolved"
    aliases = _alias_entries(alias_mapping)
    if evidence_ref:
        entries = [
            entry for entry in aliases if entry.get("evidence_ref") == evidence_ref
        ]
        if len(entries) == 1:
            bound = _bound_quote_for_alias(entries[0], quote, evidence_items)
            if bound is not None:
                return bound, "bound"
        if allow_ref_rebound:
            rebound = _unique_bound_quote_from_aliases(
                aliases,
                quote,
                evidence_items,
            )
            if rebound is not None:
                return (
                    _BoundQuote(
                        evidence_id=rebound.evidence_id,
                        evidence_ref=rebound.evidence_ref,
                        item=rebound.item,
                        span=rebound.span,
                        binding_status="evidence_ref_rebound",
                    ),
                    "evidence_ref_rebound",
                )
        return None, (
            "evidence_ref_quote_mismatch" if aliases else "evidence_ref_unresolved"
        )

    matches: dict[str, list[_BoundQuote]] = {}
    for item in evidence_items:
        text = evidence_item_text(item)
        try:
            evidence_id = identity_of(item).key
        except ValueError:
            continue
        for span in canonical_quote_spans(item, quote, text=text):
            matches.setdefault(span.identity, []).append(
                _BoundQuote(
                    evidence_id=evidence_id,
                    evidence_ref="",
                    item=item,
                    span=span,
                )
            )
    if len(matches) != 1:
        return None, "quote_identity_unresolved"
    candidates = next(iter(matches.values()))
    return (
        min(
            candidates,
            key=lambda value: (
                len(evidence_item_text(value.item)),
                value.span.text_hash,
            ),
        ),
        "bound",
    )


def _unique_bound_quote_from_aliases(
    aliases: list[dict[str, Any]],
    quote: str,
    evidence_items: list[dict[str, Any]],
) -> _BoundQuote | None:
    matches: dict[str, list[_BoundQuote]] = {}
    for entry in aliases:
        bound = _bound_quote_for_alias(entry, quote, evidence_items)
        if bound is not None:
            matches.setdefault(bound.span.identity, []).append(bound)
    if len(matches) != 1:
        return None
    return min(
        next(iter(matches.values())),
        key=lambda value: (
            value.evidence_ref,
            len(evidence_item_text(value.item)),
            value.span.text_hash,
        ),
    )


def _bound_quote_for_alias(
    entry: dict[str, Any],
    quote: str,
    evidence_items: list[dict[str, Any]],
) -> _BoundQuote | None:
    runtime_evidence_id = str(entry.get("runtime_evidence_id") or "").strip()
    item_start = _optional_int(entry.get("item_span_start"))
    item_end = _optional_int(entry.get("item_span_end"))
    if item_start is None or item_end is None:
        return None
    matching_items = []
    for item in evidence_items:
        try:
            if identity_of(item).key == runtime_evidence_id:
                matching_items.append(item)
        except ValueError:
            continue
    if len(matching_items) != 1:
        return None
    item = matching_items[0]
    text = evidence_item_text(item)
    if not (0 <= item_start < item_end <= len(text)):
        return None
    bounded = " ".join(text[item_start:item_end].casefold().split())
    normalized_quote = " ".join(str(quote or "").casefold().split())
    if not normalized_quote or normalized_quote not in bounded:
        return None
    spans = [
        span
        for span in canonical_quote_spans(item, quote, text=text)
        if item_start <= span.item_start and span.item_end <= item_end
    ]
    if len(spans) != 1:
        return None
    return _BoundQuote(
        evidence_id=runtime_evidence_id,
        evidence_ref=str(entry.get("evidence_ref") or ""),
        item=item,
        span=spans[0],
    )


def _alias_entries(value: str) -> list[dict[str, Any]]:
    try:
        payload = json.loads(str(value or ""))
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [entry for entry in payload if isinstance(entry, dict)]


def _optional_int(value: Any) -> int | None:
    if value in (None, "") or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
