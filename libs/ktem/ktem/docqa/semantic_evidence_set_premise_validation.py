from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from copy import deepcopy
from typing import Any, TypeAlias

from .boolean_authority_schema import BooleanEvidenceAuthority
from .boolean_evidence_scope import (
    _actor,
    _scope_rejection,
    _section_role,
    evidence_item_text,
)
from .evidence_identity import identity_of
from .polarity_contradiction_check import polarity_contradiction_check
from .query_phrase_extraction import source_page_locator
from .question_proposition import (
    PROPOSITION_EVIDENCE_SLOTS,
    applicable_proposition_evidence_slots,
    build_question_proposition,
    not_applicable_proposition_evidence_slots,
    proposition_evidence_bindings,
    typed_conclusion,
)
from .semantic_evidence_set_frozen_premises import validated_frozen_plan_premises
from .semantic_evidence_set_premise_support import optional_int as _optional_int
from .semantic_evidence_set_premise_support import premises_overlap as _premises_overlap
from .semantic_evidence_set_premise_support import (
    required_slot_ids as _required_slot_ids,
)
from .semantic_evidence_set_scope import semantic_scope_basis
from .semantic_relation_clause_validation import (
    semantic_relation_clause_analysis,
    semantic_slot_evidence_projection,
)

ValidatedPremises: TypeAlias = tuple[
    tuple[BooleanEvidenceAuthority, ...] | None,
    dict[str, tuple[str, ...]],
    str,
    str,
]


def validated_semantic_premises(
    request: Any,
    question: str,
    verdict: str,
    raw_premises: Any,
    items: list[dict[str, Any]],
    *,
    proof_mode: str,
    canonical_plan_projection: Any | None = None,
) -> ValidatedPremises:
    if not isinstance(raw_premises, list) or any(
        not isinstance(value, Mapping) for value in raw_premises
    ):
        return None, {}, "", "semantic_premise_schema_invalid"
    if not _premise_count_valid(proof_mode, len(raw_premises)):
        return None, {}, "", "semantic_premise_count_invalid"
    if canonical_plan_projection is not None:
        return validated_frozen_plan_premises(
            request,
            question,
            verdict,
            raw_premises,
            items,
            proof_mode=proof_mode,
            canonical_plan_projection=canonical_plan_projection,
        )
    required_slots = _required_slot_ids(request)
    if not required_slots:
        return None, {}, "", "semantic_required_slots_missing"
    lookup = _canonical_item_lookup(items)
    proposition = build_question_proposition(question)
    canonical_bindings = proposition_evidence_bindings(proposition)
    applicable_proposition_slots = set(
        applicable_proposition_evidence_slots(proposition)
    )
    evidence_relation = _evidence_relation(verdict)
    premises: list[BooleanEvidenceAuthority] = []
    slot_support: dict[str, tuple[str, ...]] = {}
    fragments: set[str] = set()
    for record in raw_premises:
        supports, fragment, proposition_bindings, reason = _premise_binding(
            record,
            required_slots,
            fragments,
            canonical_bindings=canonical_bindings,
            applicable_proposition_slots=applicable_proposition_slots,
            evidence_relation=evidence_relation,
        )
        if reason:
            return None, {}, "", reason
        authority, reason = _validated_semantic_premise(
            question,
            verdict,
            record,
            lookup,
            proposition_bindings=proposition_bindings,
            evidence_relation=evidence_relation,
        )
        if authority is None:
            return None, {}, "", reason
        fragments.add(fragment)
        premises.append(authority)
        slot_support[authority.evidence_ref] = supports
    set_reason = _premise_set_validation_reason(question, verdict, premises)
    if set_reason:
        return None, {}, "", set_reason
    scope_basis = semantic_scope_basis(question, premises)
    if not scope_basis:
        return None, {}, "", "semantic_proposition_scope_incomplete"
    covered_slots = {slot for values in slot_support.values() for slot in values}
    if covered_slots != required_slots:
        return None, {}, "", "semantic_required_slot_coverage_incomplete"
    covered_proposition_slots = {
        slot
        for premise in premises
        for slot, _value in premise.proposition_slot_bindings
    }
    if covered_proposition_slots != applicable_proposition_slots:
        return None, {}, "", "semantic_proposition_slot_coverage_incomplete"
    return tuple(premises), slot_support, scope_basis, ""


def _premise_count_valid(proof_mode: str, count: int) -> bool:
    return bool(
        (proof_mode == "atomic_semantic" and count == 1)
        or (proof_mode == "composite_conjunction" and 2 <= count <= 4)
    )


def _premise_binding(
    record: Mapping[str, Any],
    required_slots: set[str],
    existing_fragments: set[str],
    *,
    canonical_bindings: dict[str, str],
    applicable_proposition_slots: set[str],
    evidence_relation: str,
) -> tuple[tuple[str, ...], str, tuple[tuple[str, str], ...], str]:
    raw_supports = record.get("supports_slot_ids")
    if not isinstance(raw_supports, list):
        return (), "", (), "semantic_premise_slot_binding_invalid"
    supports = tuple(
        dict.fromkeys(
            str(value).strip()
            for value in raw_supports
            if isinstance(value, str) and value.strip()
        )
    )
    if not supports or any(value not in required_slots for value in supports):
        return (), "", (), "semantic_premise_slot_binding_invalid"
    raw_proposition_slots = record.get("binds_proposition_slots")
    raw_bindings = record.get("proposition_slot_bindings")
    if (
        not isinstance(raw_proposition_slots, list)
        or not raw_proposition_slots
        or len(set(raw_proposition_slots)) != len(raw_proposition_slots)
        or any(
            slot not in applicable_proposition_slots for slot in raw_proposition_slots
        )
        or not isinstance(raw_bindings, Mapping)
    ):
        return (), "", (), "semantic_premise_proposition_binding_invalid"
    expected_bindings = {
        slot: canonical_bindings[slot] for slot in raw_proposition_slots
    }
    if dict(raw_bindings) != expected_bindings:
        return (), "", (), "semantic_premise_proposition_binding_invalid"
    if record.get("evidence_relation") != evidence_relation:
        return (), "", (), "semantic_premise_evidence_relation_invalid"
    fragment = str(record.get("proposition_fragment") or "").strip()
    normalized = " ".join(fragment.casefold().split())
    if not fragment or len(fragment) > 320 or normalized in existing_fragments:
        return (), "", (), "semantic_premise_fragment_invalid"
    return (
        supports,
        normalized,
        tuple((slot, expected_bindings[slot]) for slot in raw_proposition_slots),
        "",
    )


def _premise_set_validation_reason(
    question: str,
    verdict: str,
    premises: list[BooleanEvidenceAuthority],
) -> str:
    if len({value.evidence_ref for value in premises}) != len(premises):
        return "semantic_premise_duplicate"
    if len({value.source_id for value in premises}) != 1:
        return "semantic_premise_cross_source"
    if _premises_overlap(premises):
        return "semantic_premise_overlap"
    if verdict == "no":
        conclusion = typed_conclusion(build_question_proposition(question), "no")
        polarity_check = polarity_contradiction_check(
            conclusion,
            [{"quote": value.quote} for value in premises],
        )
        if polarity_check["status"] != "aligned":
            return "semantic_negative_authority_not_explicit"
    return ""


def _canonical_item_lookup(
    items: list[dict[str, Any]],
) -> dict[str, dict[str, Any] | None]:
    lookup: dict[str, dict[str, Any] | None] = {}
    for item in items:
        try:
            evidence_id = identity_of(item).key
        except ValueError:
            continue
        lookup[evidence_id] = item if evidence_id not in lookup else None
    return lookup


def _validated_semantic_premise(
    question: str,
    verdict: str,
    record: Mapping[str, Any],
    lookup: dict[str, dict[str, Any] | None],
    *,
    proposition_bindings: tuple[tuple[str, str], ...],
    evidence_relation: str,
) -> tuple[BooleanEvidenceAuthority | None, str]:
    evidence_id = str(record.get("evidence_id") or "").strip()
    item = lookup.get(evidence_id)
    if item is None:
        return None, "semantic_premise_identity_unresolved"
    quote, start, end, canonical_start, canonical_end, reason = _bound_offsets(
        record, item
    )
    if reason:
        return None, reason
    section_scope = _section_role(item, quote)
    actor = _actor(quote, section_scope)
    if _semantic_scope_rejected(question, quote, actor, section_scope):
        return None, "semantic_premise_scope_rejected"
    actor = actor if actor != "unknown" else "local_source"
    section_scope = section_scope if section_scope != "unknown" else "document"
    source_id, page_label = source_page_locator(item)
    ref_start = canonical_start if canonical_start is not None else start
    ref_end = canonical_end if canonical_end is not None else end
    evidence_ref = f"{evidence_id}#quote:{ref_start}:{ref_end}"
    return (
        BooleanEvidenceAuthority(
            evidence_id=evidence_id,
            evidence_ref=evidence_ref,
            span_id=evidence_ref,
            quote=quote,
            span_start=start,
            span_end=end,
            canonical_start=canonical_start,
            canonical_end=canonical_end,
            actor=actor,
            section_scope=section_scope,
            relation="semantic_premise",
            object=str(record.get("proposition_fragment") or "").strip(),
            quantifier="none",
            polarity=verdict,
            reason="semantic_evidence_set_premise",
            qualifier="none",
            source_id=source_id,
            page_label=page_label,
            proposition_slot_bindings=proposition_bindings,
            evidence_relation=evidence_relation,
        ),
        "",
    )


def semantic_proposition_binding_fields(
    question: str,
    verdict: str,
    premises: tuple[BooleanEvidenceAuthority, ...],
    *,
    canonical_plan_projection: Any | None = None,
) -> dict[str, Any]:
    if canonical_plan_projection is not None:
        return _frozen_plan_binding_fields(
            verdict,
            canonical_plan_projection,
            premises,
        )
    proposition = build_question_proposition(question)
    applicable_slots = applicable_proposition_evidence_slots(proposition)
    not_applicable_slots = not_applicable_proposition_evidence_slots(proposition)
    premise_slot_evidence = {
        premise.evidence_ref: _semantic_premise_slot_evidence(premise, proposition)
        for premise in premises
    }
    slot_refs = {
        slot: sorted(
            premise_slot_evidence[premise.evidence_ref][slot]["evidence_ref"]
            for premise in premises
            if slot in dict(premise.proposition_slot_bindings)
        )
        for slot in applicable_slots
    }
    bindings = {
        slot: next(
            (
                dict(premise.proposition_slot_bindings)[slot]
                for premise in premises
                if slot in dict(premise.proposition_slot_bindings)
            ),
            "",
        )
        for slot in applicable_slots
    }
    evidence_refs = sorted(premise.evidence_ref for premise in premises)
    payload = {
        "evidence_relation": _evidence_relation(verdict),
        "proposition_slot_bindings": bindings,
        "proposition_slot_evidence_refs": slot_refs,
        "proposition_binding_evidence_set_refs": evidence_refs,
        "not_applicable_proposition_slots": list(not_applicable_slots),
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return {
        **payload,
        "required_proposition_slots": list(applicable_slots),
        "proposition_slot_evidence": premise_slot_evidence,
        "proposition_evidence_set_digest": hashlib.sha256(
            canonical.encode("utf-8")
        ).hexdigest(),
    }


def _semantic_premise_slot_evidence(
    premise: BooleanEvidenceAuthority,
    proposition: Any,
    *,
    canonical_plan_projection: Any | None = None,
) -> dict[str, dict[str, Any]]:
    if canonical_plan_projection is not None:
        for index, projected in enumerate(canonical_plan_projection.premises, start=1):
            if (
                projected.get("evidence_id") == premise.evidence_id
                and projected.get("span_selector")
                == str(premise.evidence_ref).split("#quote:", 1)[0]
            ):
                return deepcopy(
                    canonical_plan_projection.slot_evidence.get(
                        str(projected.get("span_selector") or ""), {}
                    )
                )
        return {}
    analysis = semantic_relation_clause_analysis(
        {
            "quote": premise.quote,
            "binds_proposition_slots": [
                slot for slot, _value in premise.proposition_slot_bindings
            ],
            "proposition_slot_bindings": dict(premise.proposition_slot_bindings),
            "evidence_relation": premise.evidence_relation,
        },
        proposition,
    )
    span_base = (
        premise.canonical_start
        if premise.canonical_start is not None
        else premise.span_start
    )
    return semantic_slot_evidence_projection(
        analysis,
        premise_ref=premise.evidence_ref,
        span_base=span_base,
    )


def _frozen_plan_binding_fields(
    verdict: str,
    projection: Any,
    premises: tuple[BooleanEvidenceAuthority, ...],
) -> dict[str, Any]:
    premise_slot_evidence = {
        premise.evidence_ref: _frozen_plan_authority_slot_evidence(
            premise,
            projection,
        )
        for premise in premises
    }
    applicable_slots = list(projection.required_slots)
    slot_refs = {
        slot: sorted(
            premise_slot_evidence[premise.evidence_ref][slot]["evidence_ref"]
            for premise in premises
            if slot in dict(premise.proposition_slot_bindings)
        )
        for slot in applicable_slots
    }
    bindings = {
        slot: str(projection.proposition_slot_bindings.get(slot) or "")
        for slot in applicable_slots
    }
    evidence_refs = sorted(premise.evidence_ref for premise in premises)
    payload = {
        "evidence_relation": projection.polarity_relation,
        "proposition_slot_bindings": bindings,
        "proposition_slot_evidence_refs": slot_refs,
        "proposition_binding_evidence_set_refs": evidence_refs,
        "not_applicable_proposition_slots": [
            slot for slot in PROPOSITION_EVIDENCE_SLOTS if slot not in applicable_slots
        ],
    }
    return {
        **payload,
        "required_proposition_slots": applicable_slots,
        "proposition_slot_evidence": premise_slot_evidence,
        "proposition_evidence_set_digest": hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest(),
        "canonical_evidence_plan_id": projection.plan_id,
        "canonical_plan_digest": projection.plan_digest,
        "canonical_projection_digest": hashlib.sha256(
            json.dumps(
                projection.as_dict(), sort_keys=True, separators=(",", ":")
            ).encode("utf-8")
        ).hexdigest(),
    }


def _frozen_plan_authority_slot_evidence(
    premise: BooleanEvidenceAuthority,
    projection: Any,
) -> dict[str, dict[str, Any]]:
    selector = ""
    for projected in projection.premises:
        if (
            projected.get("evidence_id") == premise.evidence_id
            and projected.get("span_start") == premise.span_start
            and projected.get("span_end") == premise.span_end
        ):
            selector = str(projected.get("span_selector") or "")
            break
    if not selector:
        return {}
    output: dict[str, dict[str, Any]] = {}
    for slot, span in projection.slot_evidence.get(selector, {}).items():
        start = _optional_int(span.get("span_start"))
        end = _optional_int(span.get("span_end"))
        if start is None or end is None:
            continue
        output[str(slot)] = {
            **dict(span),
            "evidence_ref": f"{premise.evidence_ref}#slot:{slot}:{start}:{end}",
        }
    return output


def _evidence_relation(verdict: str) -> str:
    return {
        "yes": "proposition_support",
        "no": "explicit_contradiction",
    }.get(str(verdict or ""), "undetermined")


def _bound_offsets(
    record: Mapping[str, Any],
    item: dict[str, Any],
) -> tuple[str, int, int, int | None, int | None, str]:
    quote = str(record.get("quote") or "").strip()
    start = _optional_int(record.get("span_start"))
    end = _optional_int(record.get("span_end"))
    text = evidence_item_text(item)
    if (
        not quote
        or len(quote) > 640
        or start is None
        or end is None
        or start < 0
        or end <= start
        or text[start:end] != quote
    ):
        return "", -1, -1, None, None, "semantic_premise_quote_unbound"
    item_start = _optional_int(item.get("canonical_start"))
    canonical_start = item_start + start if item_start is not None else None
    canonical_end = item_start + end if item_start is not None else None
    if (
        _optional_int(record.get("canonical_start")) != canonical_start
        or _optional_int(record.get("canonical_end")) != canonical_end
    ):
        return "", -1, -1, None, None, "semantic_premise_canonical_offset_unbound"
    return quote, start, end, canonical_start, canonical_end, ""


def _semantic_scope_rejected(
    question: str,
    quote: str,
    actor: str,
    section_scope: str,
) -> bool:
    scope_rejection = _scope_rejection(
        question,
        actor=actor,
        section_role=section_scope,
        structured_scope_available=section_scope != "unknown",
        quote=quote,
    )
    return bool(
        section_scope == "future_work"
        or (
            scope_rejection
            and not (
                scope_rejection == "current_paper_scope_not_established"
                and actor == "unknown"
            )
        )
    )
