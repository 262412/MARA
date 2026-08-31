from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeAlias

from .boolean_authority_schema import BooleanEvidenceAuthority
from .boolean_evidence_scope import evidence_item_text
from .evidence_identity import identity_of
from .query_phrase_extraction import source_page_locator
from .semantic_evidence_set_premise_support import (
    optional_int,
    premises_overlap,
    required_slot_ids,
)
from .semantic_evidence_set_scope import semantic_scope_basis

FrozenValidatedPremises: TypeAlias = tuple[
    tuple[BooleanEvidenceAuthority, ...] | None,
    dict[str, tuple[str, ...]],
    str,
    str,
]


def validated_frozen_plan_premises(
    request: Any,
    question: str,
    verdict: str,
    raw_premises: list[Mapping[str, Any]],
    items: list[dict[str, Any]],
    *,
    proof_mode: str,
    canonical_plan_projection: Any,
) -> FrozenValidatedPremises:
    if proof_mode != canonical_plan_projection.proof_mode:
        return None, {}, "", "semantic_premise_proof_mode_mismatch"
    frozen = canonical_plan_projection.premises
    if len(raw_premises) != len(frozen):
        return None, {}, "", "semantic_premise_count_invalid"
    lookup = _frozen_item_lookup(items)
    required_slots = required_slot_ids(request)
    premises: list[BooleanEvidenceAuthority] = []
    slot_support: dict[str, tuple[str, ...]] = {}
    covered_slots: set[str] = set()
    for raw, expected in zip(raw_premises, frozen):
        authority, supports, reason = _validated_frozen_premise(
            raw,
            expected,
            lookup,
            verdict=verdict,
            required_slots=required_slots,
        )
        if authority is None:
            return None, {}, "", reason
        premises.append(authority)
        slot_support[authority.evidence_ref] = supports
        covered_slots.update(supports)
    reason = _frozen_premise_set_reason(premises, covered_slots, required_slots)
    if reason:
        return None, {}, "", reason
    scope_basis = semantic_scope_basis(question, premises)
    if not scope_basis:
        return None, {}, "", "semantic_proposition_scope_incomplete"
    return tuple(premises), slot_support, scope_basis, ""


def _validated_frozen_premise(
    raw: Mapping[str, Any],
    expected: Mapping[str, Any],
    lookup: dict[str, dict[str, Any] | None],
    *,
    verdict: str,
    required_slots: set[str],
) -> tuple[BooleanEvidenceAuthority | None, tuple[str, ...], str]:
    if not _frozen_premise_fields_match(raw, expected):
        return None, (), "semantic_premise_projection_mismatch"
    span, reason = _validated_frozen_span(expected, lookup)
    if span is None:
        return None, (), reason
    supports = _frozen_supports(expected)
    if (
        not supports
        or len(set(supports)) != len(supports)
        or not set(supports) <= required_slots
    ):
        return None, (), "semantic_premise_slot_binding_invalid"
    return _frozen_authority(expected, span, verdict=verdict), supports, ""


def _validated_frozen_span(
    expected: Mapping[str, Any],
    lookup: dict[str, dict[str, Any] | None],
) -> tuple[dict[str, Any] | None, str]:
    evidence_id = str(expected.get("evidence_id") or "")
    item = lookup.get(evidence_id)
    if item is None:
        return None, "semantic_premise_identity_unresolved"
    quote = str(expected.get("quote") or "")
    start = optional_int(expected.get("span_start"))
    end = optional_int(expected.get("span_end"))
    if (
        not quote
        or start is None
        or end is None
        or start < 0
        or end <= start
        or evidence_item_text(item)[start:end] != quote
    ):
        return None, "semantic_premise_quote_unbound"
    ref_start = optional_int(expected.get("canonical_start"))
    ref_end = optional_int(expected.get("canonical_end"))
    ref_start = start if expected.get("canonical_start") is None else ref_start
    ref_end = end if expected.get("canonical_end") is None else ref_end
    if ref_start is None or ref_end is None:
        return None, "semantic_premise_canonical_offset_unbound"
    source_id, page_label = source_page_locator(item)
    return {
        "evidence_id": evidence_id,
        "evidence_ref": f"{evidence_id}#quote:{ref_start}:{ref_end}",
        "quote": quote,
        "span_start": start,
        "span_end": end,
        "source_id": source_id,
        "page_label": page_label,
    }, ""


def _frozen_supports(expected: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(
        str(value)
        for value in expected.get("supports_slot_ids") or []
        if str(value).strip()
    )


def _frozen_authority(
    expected: Mapping[str, Any],
    span: Mapping[str, Any],
    *,
    verdict: str,
) -> BooleanEvidenceAuthority:
    bindings = dict(expected.get("proposition_slot_bindings") or {})
    binding_pairs = tuple(
        (str(slot), str(bindings.get(slot) or ""))
        for slot in expected.get("binds_proposition_slots") or []
    )
    return BooleanEvidenceAuthority(
        evidence_id=str(span["evidence_id"]),
        evidence_ref=str(span["evidence_ref"]),
        span_id=str(span["evidence_ref"]),
        quote=str(span["quote"]),
        span_start=int(span["span_start"]),
        span_end=int(span["span_end"]),
        canonical_start=optional_int(expected.get("canonical_start")),
        canonical_end=optional_int(expected.get("canonical_end")),
        actor="current_paper",
        section_scope="document",
        relation="semantic_premise",
        object=str(expected.get("proposition_fragment") or ""),
        quantifier="none",
        polarity=verdict,
        reason="semantic_evidence_set_premise",
        qualifier="none",
        source_id=str(span["source_id"]),
        page_label=str(span["page_label"]),
        proposition_slot_bindings=binding_pairs,
        evidence_relation=str(expected.get("evidence_relation") or ""),
    )


def _frozen_premise_set_reason(
    premises: list[BooleanEvidenceAuthority],
    covered_slots: set[str],
    required_slots: set[str],
) -> str:
    if len({value.evidence_ref for value in premises}) != len(premises):
        return "semantic_premise_duplicate"
    if len({value.source_id for value in premises}) != 1:
        return "semantic_premise_cross_source"
    if premises_overlap(premises):
        return "semantic_premise_overlap"
    if covered_slots != required_slots:
        return "semantic_required_slot_coverage_incomplete"
    return ""


def _frozen_premise_fields_match(
    raw: Mapping[str, Any],
    expected: Mapping[str, Any],
) -> bool:
    fields = (
        "evidence_id",
        "span_selector",
        "quote",
        "span_start",
        "span_end",
        "canonical_start",
        "canonical_end",
        "proposition_fragment",
        "supports_slot_ids",
        "binds_proposition_slots",
        "proposition_slot_bindings",
        "evidence_relation",
        "canonical_evidence_plan_id",
        "canonical_plan_digest",
    )
    return bool(
        all(raw.get(field) == expected.get(field) for field in fields)
        and raw.get("semantic_alignment") == expected.get("semantic_alignment")
        and raw.get("proposition_slot_spans") == expected.get("proposition_slot_spans")
    )


def _frozen_item_lookup(
    items: list[dict[str, Any]],
) -> dict[str, dict[str, Any] | None]:
    lookup: dict[str, dict[str, Any] | None] = {}
    for item in items:
        try:
            identity = identity_of(item)
            keys = {
                identity.key,
                identity.legacy_key,
                str(item.get("evidence_id") or ""),
                str(item.get("canonical_id") or ""),
            }
        except ValueError:
            continue
        for key in keys - {""}:
            lookup[key] = item if key not in lookup else None
    return lookup
