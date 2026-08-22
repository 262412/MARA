from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeAlias

from .boolean_authority_schema import (
    GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
    SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
    BooleanEvidenceAuthority,
)
from .boolean_evidence_scope import (
    _actor,
    _scope_rejection,
    _section_role,
    evidence_item_text,
)
from .boolean_proposition_polarity import evidence_polarity
from .evidence_identity import identity_of
from .query_phrase_extraction import source_page_locator
from .question_proposition import (
    build_question_proposition,
    typed_conclusion,
    validate_question_proposition,
    validate_typed_conclusion,
)
from .semantic_entailment_audit import semantic_entailment_audit_validation_reason
from .semantic_evidence_set_scope import semantic_scope_basis

ValidatedPremises: TypeAlias = tuple[
    tuple[BooleanEvidenceAuthority, ...] | None,
    dict[str, tuple[str, ...]],
    str,
    str,
]


def validated_semantic_header(
    response: Mapping[str, Any],
    question: str,
    *,
    release_mode: bool,
) -> tuple[tuple[str, dict[str, Any]] | None, str]:
    verdict, proof_mode, premises, shape_reason = _semantic_response_shape(response)
    if shape_reason:
        return None, shape_reason
    proposition = build_question_proposition(question)
    question_reason = validate_question_proposition(
        response.get("question_proposition"), question
    )
    if question_reason:
        return None, question_reason
    conclusion = typed_conclusion(proposition, verdict) if verdict in {"yes", "no"} else None
    if conclusion is not None:
        conclusion_reason = validate_typed_conclusion(
            response.get("typed_conclusion"), proposition, verdict
        )
        if conclusion_reason:
            return None, conclusion_reason
    verifier = response.get("verifier")
    if not isinstance(verifier, Mapping):
        return None, "semantic_verifier_attestation_missing"
    if verifier.get("release_mode") is not release_mode:
        return None, "semantic_release_mode_binding_invalid"
    if conclusion is not None:
        audit_reason = semantic_entailment_audit_validation_reason(
            question,
            verdict,
            premises,
            response.get("entailment_audit"),
            proof_mode=proof_mode,
            proposition=proposition,
            conclusion=conclusion,
            release_mode=release_mode,
        )
        if audit_reason:
            return None, audit_reason
    model = str(verifier.get("model") or "").strip()
    if verifier.get("contract_id") != GROUNDED_SEMANTIC_VERIFIER_CONTRACT or not model:
        return None, "semantic_verifier_attestation_invalid"
    return (
        verdict,
        _verifier_attestation(
            response,
            verifier,
            verdict=verdict,
            proof_mode=proof_mode,
            proposition=proposition.as_dict(),
            conclusion=conclusion.as_dict() if conclusion is not None else {},
            release_mode=release_mode,
        ),
    ), ""


def _semantic_response_shape(
    response: Mapping[str, Any],
) -> tuple[str, str, list[Mapping[str, Any]], str]:
    if response.get("contract_id") != SEMANTIC_PROPOSITION_VERDICT_CONTRACT:
        return "", "", [], "semantic_verdict_contract_mismatch"
    verdict = str(response.get("verdict") or "")
    if verdict not in {"yes", "no", "insufficient_evidence"}:
        return "", "", [], "semantic_verdict_invalid"
    if response.get("support_mode") != "evidence_set":
        return "", "", [], "semantic_support_mode_invalid"
    proof_mode = str(response.get("proof_mode") or "")
    raw_premises = response.get("premises")
    premises = (
        [value for value in raw_premises if isinstance(value, Mapping)]
        if isinstance(raw_premises, list)
        else []
    )
    expected_count = {
        "atomic_semantic": (1, 1),
        "composite_conjunction": (2, 4),
    }.get(proof_mode)
    if verdict in {"yes", "no"} and (
        expected_count is None
        or not expected_count[0] <= len(premises) <= expected_count[1]
    ):
        return "", "", [], "semantic_proof_mode_invalid"
    if verdict == "insufficient_evidence" and (proof_mode != "none" or premises):
        return "", "", [], "semantic_proof_mode_invalid"
    if verdict in {"yes", "no"} and (
        response.get("jointly_complete") is not True
        or response.get("each_premise_required") is not True
    ):
        return "", "", [], "semantic_joint_entailment_incomplete"
    return verdict, proof_mode, premises, ""


def _verifier_attestation(
    response: Mapping[str, Any],
    verifier: Mapping[str, Any],
    *,
    verdict: str,
    proof_mode: str,
    proposition: dict[str, Any],
    conclusion: dict[str, Any],
    release_mode: bool,
) -> dict[str, Any]:
    return {
        "contract_id": GROUNDED_SEMANTIC_VERIFIER_CONTRACT,
        "verdict_contract_id": SEMANTIC_PROPOSITION_VERDICT_CONTRACT,
        "model": str(verifier.get("model") or "").strip(),
        "seed": verifier.get("seed"),
        "verdict": verdict,
        "jointly_complete": response.get("jointly_complete") is True,
        "each_premise_required": response.get("each_premise_required") is True,
        "proof_mode": proof_mode,
        "question_proposition": proposition,
        "typed_conclusion": conclusion,
        "semantic_pack_digest": str(verifier.get("semantic_pack_digest") or ""),
        "auditor_relationship": str(verifier.get("auditor_relationship") or ""),
        "release_mode": release_mode,
        "entailment_audit": dict(response.get("entailment_audit") or {}),
    }


def validated_semantic_premises(
    request: Any,
    question: str,
    verdict: str,
    raw_premises: Any,
    items: list[dict[str, Any]],
    *,
    proof_mode: str,
) -> ValidatedPremises:
    if not isinstance(raw_premises, list) or any(
        not isinstance(value, Mapping) for value in raw_premises
    ):
        return None, {}, "", "semantic_premise_schema_invalid"
    if not _premise_count_valid(proof_mode, len(raw_premises)):
        return None, {}, "", "semantic_premise_count_invalid"
    required_slots = _required_slot_ids(request)
    if not required_slots:
        return None, {}, "", "semantic_required_slots_missing"
    lookup = _canonical_item_lookup(items)
    premises: list[BooleanEvidenceAuthority] = []
    slot_support: dict[str, tuple[str, ...]] = {}
    fragments: set[str] = set()
    for record in raw_premises:
        authority, reason = _validated_semantic_premise(
            question, verdict, record, lookup
        )
        if authority is None:
            return None, {}, "", reason
        supports, fragment, reason = _premise_binding(
            record, required_slots, fragments
        )
        if reason:
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
) -> tuple[tuple[str, ...], str, str]:
    raw_supports = record.get("supports_slot_ids")
    if not isinstance(raw_supports, list):
        return (), "", "semantic_premise_slot_binding_invalid"
    supports = tuple(
        dict.fromkeys(
            str(value).strip()
            for value in raw_supports
            if isinstance(value, str) and value.strip()
        )
    )
    if not supports or any(value not in required_slots for value in supports):
        return (), "", "semantic_premise_slot_binding_invalid"
    fragment = str(record.get("proposition_fragment") or "").strip()
    normalized = " ".join(fragment.casefold().split())
    if not fragment or len(fragment) > 320 or normalized in existing_fragments:
        return (), "", "semantic_premise_fragment_invalid"
    return supports, normalized, ""


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
    if verdict == "no" and evidence_polarity(
        question,
        " ".join(value.quote for value in premises),
        desired_polarity="no",
    ) != "no":
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
    return BooleanEvidenceAuthority(
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
    ), ""


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


def _premises_overlap(premises: list[BooleanEvidenceAuthority]) -> bool:
    for index, left in enumerate(premises):
        for right in premises[index + 1 :]:
            if left.evidence_id == right.evidence_id and max(
                left.span_start, right.span_start
            ) < min(left.span_end, right.span_end):
                return True
    return False


def _required_slot_ids(request: Any) -> set[str]:
    plan = getattr(request, "query_plan", None)
    slots = (
        plan.get("evidence_slots", [])
        if isinstance(plan, Mapping)
        else getattr(plan, "evidence_slots", ()) or ()
    )
    return {
        _slot_value(slot, "slot_id")
        for slot in slots
        if _slot_required(slot) and _slot_value(slot, "slot_id")
    }


def _slot_value(slot: Any, key: str) -> str:
    raw = slot.get(key) if isinstance(slot, Mapping) else getattr(slot, key, "")
    return str(raw or "").strip()


def _slot_required(slot: Any) -> bool:
    return bool(
        slot.get("required_for_verification", False)
        if isinstance(slot, Mapping)
        else getattr(slot, "required_for_verification", False)
    )


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None and str(value).strip() else None
    except (TypeError, ValueError):
        return None
