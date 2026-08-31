"""The one downstream projection of a frozen canonical proposition plan.

The candidate planner is the owner of semantic decisions. Consumers of a
frozen QASPER plan validate persisted identity and copy persisted semantic
fields; this module deliberately does not call a quote clause analyser or a
token matcher.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any, NamedTuple

from .canonical_proposition_evidence_plan_contract import canonical_plan_digest
from .canonical_serialization import canonical_projection_digest
from .frozen_canonical_projection_model import (
    FROZEN_CANONICAL_PROJECTION_CONTRACT,
    FrozenCanonicalPropositionEvidencePlan,
)
from .frozen_canonical_projection_utils import (  # noqa: F401 - compatibility re-export
    frozen_slot_support_by_ref,
    nonempty_string,
    proof_mode,
    slot_refs,
    string_tuple,
    token_tuple,
)
from .frozen_canonical_projection_validation import comparison_relation_reason
from .frozen_canonical_projection_validation import event_subplans as _event_subplans
from .frozen_canonical_projection_validation import selector_lookup
from .frozen_canonical_projection_validation import (
    selector_projection_reason as _selector_projection_reason,
)
from .qasper_semantic_pack_contract import (
    QASPER_CANONICAL_SEMANTIC_PACK_METADATA_KEY,
    qasper_canonical_records_reason,
)
from .question_proposition import (
    PROPOSITION_EVIDENCE_SLOTS,
    QuestionProposition,
    applicable_proposition_evidence_slots,
    proposition_evidence_bindings,
)


class _PlanHeader(NamedTuple):
    plan_id: str
    relation: str
    plan_digest: str
    span_refs: tuple[str, ...]
    slot_refs: dict[str, tuple[str, ...]]
    expected_slots: tuple[str, ...]
    required_tokens: tuple[str, ...]
    covered_tokens: tuple[str, ...]
    proof_mode: str


class _PlanEvents(NamedTuple):
    event_binding_id: str
    event_subplans: tuple[dict[str, Any], ...]


class _ProjectedPremise(NamedTuple):
    premise: dict[str, Any]
    slot_evidence: dict[str, dict[str, Any]]
    audit_slot_evidence: dict[str, dict[str, Any]]
    covered_tokens: tuple[str, ...]
    alignment: dict[str, Any]


class _PlanPremises(NamedTuple):
    premises: tuple[dict[str, Any], ...]
    slot_evidence: dict[str, dict[str, dict[str, Any]]]
    audit_slot_evidence: dict[str, dict[str, dict[str, Any]]]
    covered_tokens_by_ref: dict[str, tuple[str, ...]]
    semantic_alignment_by_ref: dict[str, dict[str, Any]]


def frozen_canonical_plan_projection(
    plan: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
    *,
    proposition: QuestionProposition | None = None,
    expected_slots: Sequence[str] | None = None,
    expected_plan_digest: str = "",
    slot_support_by_ref: Mapping[str, Sequence[str]] | None = None,
) -> FrozenCanonicalPropositionEvidencePlan | None:
    """Return the validated projection, or ``None`` on any identity defect."""

    projection, _reason = frozen_canonical_plan_projection_checked(
        plan,
        records,
        proposition=proposition,
        expected_slots=expected_slots,
        expected_plan_digest=expected_plan_digest,
        slot_support_by_ref=slot_support_by_ref,
    )
    return projection


def frozen_canonical_plan_projection_checked(
    plan: Mapping[str, Any],
    records: Sequence[Mapping[str, Any]],
    *,
    proposition: QuestionProposition | None = None,
    expected_slots: Sequence[str] | None = None,
    expected_plan_digest: str = "",
    slot_support_by_ref: Mapping[str, Sequence[str]] | None = None,
) -> tuple[FrozenCanonicalPropositionEvidencePlan | None, str]:
    """Validate the frozen plan and return a stable failure reason."""

    header, reason = _plan_header(
        plan,
        records,
        proposition=proposition,
        expected_slots=expected_slots,
        expected_plan_digest=expected_plan_digest,
    )
    if header is None:
        return None, reason or "canonical_plan_projection_invalid"
    selectors = selector_lookup(records)
    if selectors is None or any(ref not in selectors for ref in header.span_refs):
        return None, "canonical_plan_projection_span_invalid"
    ref_slots = _reference_slots(header)
    if ref_slots is None:
        return None, "canonical_plan_projection_slot_refs_invalid"
    events, reason = _plan_events(
        plan,
        header,
        selectors,
        proposition=proposition,
    )
    if events is None:
        return None, reason or "canonical_plan_projection_event_invalid"
    if comparison_relation_reason(
        plan.get("comparison_relation"),
        event_subplans=events.event_subplans,
        polarity_relation=header.relation,
    ):
        return None, "canonical_plan_projection_comparison_invalid"
    projected, reason = _project_plan_premises(
        selectors,
        header,
        ref_slots,
        slot_support_by_ref=slot_support_by_ref,
        proposition=proposition,
    )
    if projected is None:
        return None, reason or "canonical_plan_projection_premise_invalid"
    return _make_projection(header, events, projected, plan), ""


def _plan_header(
    plan: Any,
    records: Sequence[Mapping[str, Any]],
    *,
    proposition: QuestionProposition | None,
    expected_slots: Sequence[str] | None,
    expected_plan_digest: str,
) -> tuple[_PlanHeader | None, str]:
    if not isinstance(plan, Mapping):
        return None, "canonical_plan_projection_invalid"
    if qasper_canonical_records_reason(records):
        return None, "canonical_plan_projection_frozen_records_invalid"
    identity, reason = _plan_identity(plan, expected_plan_digest)
    if identity is None:
        return None, reason or "canonical_plan_projection_invalid"
    plan_id, relation, plan_digest = identity
    spans = string_tuple(plan.get("span_refs"))
    if not 1 <= len(spans) <= 4 or len(set(spans)) != len(spans):
        return None, "canonical_plan_projection_span_invalid"
    refs = slot_refs(plan.get("slot_refs"), spans)
    if refs is None:
        return None, "canonical_plan_projection_slot_refs_invalid"
    expected, reason = _plan_slots(refs, proposition, expected_slots)
    if reason:
        return None, reason
    required = token_tuple(plan.get("required_object_tokens"))
    covered = token_tuple(plan.get("covered_object_tokens"))
    if not _token_coverage_valid(required, covered):
        return None, "canonical_plan_projection_token_coverage_invalid"
    resolved_proof_mode = proof_mode(plan.get("proof_mode"), len(spans))
    if resolved_proof_mode is None:
        return None, "canonical_plan_projection_proof_mode_invalid"
    return (
        _PlanHeader(
            plan_id,
            relation,
            plan_digest,
            spans,
            refs,
            expected,
            required,
            covered,
            resolved_proof_mode,
        ),
        "",
    )


def _plan_identity(
    plan: Mapping[str, Any],
    expected_plan_digest: str,
) -> tuple[tuple[str, str, str] | None, str]:
    plan_id = nonempty_string(plan.get("plan_id"))
    relation = nonempty_string(plan.get("polarity_relation"))
    if not plan_id or relation not in {
        "proposition_support",
        "explicit_contradiction",
    }:
        return None, "canonical_plan_projection_invalid"
    payload = deepcopy(dict(plan))
    declared = nonempty_string(payload.pop("plan_digest", ""))
    canonical = nonempty_string(payload.pop("canonical_plan_digest", ""))
    # CanonicalEvidenceSetPlan exposes its child digest as ``plan_id``.
    plan_digest = declared or canonical or plan_id
    if (declared and declared != plan_id) or (canonical and canonical != plan_id):
        return None, "canonical_plan_projection_digest_mismatch"
    if expected_plan_digest and expected_plan_digest != plan_digest:
        return None, "canonical_plan_projection_digest_mismatch"
    return (plan_id, relation, plan_digest), ""


def _plan_slots(
    refs: dict[str, tuple[str, ...]] | None,
    proposition: QuestionProposition | None,
    expected_slots: Sequence[str] | None,
) -> tuple[tuple[str, ...], str]:
    if refs is None:
        return (), "canonical_plan_projection_slot_refs_invalid"
    declared = tuple(slot for slot in PROPOSITION_EVIDENCE_SLOTS if slot in refs)
    expected = (
        tuple(expected_slots)
        if expected_slots is not None
        else (
            applicable_proposition_evidence_slots(proposition)
            if proposition is not None
            else declared
        )
    )
    if (
        set(refs) != set(declared)
        or not expected
        or set(expected) != set(declared)
        or tuple(slot for slot in expected if slot in PROPOSITION_EVIDENCE_SLOTS)
        != expected
    ):
        return (), "canonical_plan_projection_slot_refs_invalid"
    return expected, ""


def _token_coverage_valid(
    required: tuple[str, ...],
    covered: tuple[str, ...],
) -> bool:
    return bool(
        required
        and len(set(required)) == len(required)
        and len(set(covered)) == len(covered)
        and set(covered) <= set(required)
        and set(covered) == set(required)
    )


def _reference_slots(
    header: _PlanHeader,
) -> dict[str, tuple[str, ...]] | None:
    expected = {
        ref: tuple(
            slot for slot in header.expected_slots if ref in header.slot_refs[slot]
        )
        for ref in header.span_refs
    }
    return expected if all(expected.values()) else None


def _plan_events(
    plan: Mapping[str, Any],
    header: _PlanHeader,
    selectors: Mapping[str, Mapping[str, Any]],
    *,
    proposition: QuestionProposition | None,
) -> tuple[_PlanEvents | None, str]:
    event_ids = {str(selectors[ref].get("event_id") or "") for ref in header.span_refs}
    if not event_ids or "" in event_ids:
        return None, "canonical_plan_projection_event_invalid"
    subplans, reason = _event_subplans(
        plan.get("event_subplans"),
        span_refs=header.span_refs,
        slot_refs=header.slot_refs,
        required_tokens=header.required_tokens,
        covered_tokens=header.covered_tokens,
        event_id_by_ref={
            ref: str(selectors[ref].get("event_id") or "") for ref in header.span_refs
        },
        proposition=proposition,
    )
    if reason or {str(item.get("event_id")) for item in subplans} != event_ids:
        return None, reason or "canonical_plan_projection_event_invalid"
    binding = nonempty_string(plan.get("event_binding_id"))
    if not binding:
        return None, "canonical_plan_projection_event_invalid"
    if proposition is not None and binding != _event_binding_digest(
        proposition,
        subplans,
        plan.get("comparison_relation"),
    ):
        return None, "canonical_plan_projection_event_invalid"
    return _PlanEvents(binding, subplans), ""


def _event_binding_digest(
    proposition: QuestionProposition,
    subplans: Sequence[Mapping[str, Any]],
    comparison: Any,
) -> str:
    return canonical_plan_digest(
        {
            "proposition_id": proposition.proposition_id,
            "event_subplans": [
                {key: value for key, value in subplan.items() if key != "contract_id"}
                for subplan in subplans
            ],
            "comparison_relation": (
                {
                    key: value
                    for key, value in dict(comparison or {}).items()
                    if key != "contract_id"
                }
                if isinstance(comparison, Mapping)
                else comparison
            ),
        }
    )


def _project_plan_premises(
    selectors: Mapping[str, Mapping[str, Any]],
    header: _PlanHeader,
    ref_slots: Mapping[str, tuple[str, ...]],
    *,
    slot_support_by_ref: Mapping[str, Sequence[str]] | None,
    proposition: QuestionProposition | None,
) -> tuple[_PlanPremises | None, str]:
    projected: list[_ProjectedPremise] = []
    for index, ref in enumerate(header.span_refs, start=1):
        item, reason = _project_plan_premise(
            selectors[ref],
            header,
            ref,
            ref_slots[ref],
            index=index,
            slot_support_by_ref=slot_support_by_ref,
            proposition=proposition,
        )
        if item is None:
            return None, reason or "canonical_plan_projection_premise_invalid"
        projected.append(item)
    if set().union(*(set(item.covered_tokens) for item in projected)) != set(
        header.covered_tokens
    ):
        return None, "canonical_plan_projection_token_coverage_invalid"
    return _collect_projected_premises(header.span_refs, projected), ""


def _project_plan_premise(
    selector: Mapping[str, Any],
    header: _PlanHeader,
    ref: str,
    expected_slots: tuple[str, ...],
    *,
    index: int,
    slot_support_by_ref: Mapping[str, Sequence[str]] | None,
    proposition: QuestionProposition | None,
) -> tuple[_ProjectedPremise | None, str]:
    reason = _selector_projection_reason(
        selector,
        evidence_id=str(selector.get("evidence_id") or ""),
        selector_id=ref,
        expected_relation=header.relation,
        expected_required_tokens=header.required_tokens,
        expected_slots=expected_slots,
        proposition=proposition,
    )
    if reason:
        return None, reason
    alignment = deepcopy(dict(selector["semantic_alignment"]))
    covered = token_tuple(alignment.get("covered_object_tokens"))
    raw_spans = deepcopy(dict(selector["proposition_slot_spans"]))
    slot_evidence = {slot: dict(raw_spans[slot]) for slot in expected_slots}
    audit = {
        slot: _audit_slot(span, index=index, slot=slot)
        for slot, span in slot_evidence.items()
    }
    bindings = proposition_evidence_bindings(proposition) if proposition else {}
    premise_bindings = {
        slot: str(bindings[slot]) for slot in expected_slots if slot in bindings
    }
    supports = tuple(
        str(value).strip()
        for value in (slot_support_by_ref or {}).get(ref, ())
        if str(value).strip()
    )
    premise = _premise_record(
        selector,
        header,
        ref,
        expected_slots,
        index=index,
        raw_spans=raw_spans,
        premise_bindings=premise_bindings,
        supports=supports,
        alignment=alignment,
    )
    return _ProjectedPremise(premise, slot_evidence, audit, covered, alignment), ""


def _audit_slot(
    span: Mapping[str, Any],
    *,
    index: int,
    slot: str,
) -> dict[str, Any]:
    return {
        "text": str(span["text"]),
        "span_start": int(span["span_start"]),
        "span_end": int(span["span_end"]),
        "clause_ref": str(span["clause_ref"]),
        "clause_start": int(span["clause_start"]),
        "clause_end": int(span["clause_end"]),
        "evidence_ref": f"P{index}:{slot}",
    }


def _premise_record(
    selector: Mapping[str, Any],
    header: _PlanHeader,
    ref: str,
    expected_slots: tuple[str, ...],
    *,
    index: int,
    raw_spans: dict[str, Any],
    premise_bindings: dict[str, str],
    supports: tuple[str, ...],
    alignment: dict[str, Any],
) -> dict[str, Any]:
    return {
        "evidence_id": str(selector["evidence_id"]),
        "span_selector": ref,
        "quote": str(selector["text"]),
        "span_start": int(selector["span_start"]),
        "span_end": int(selector["span_end"]),
        "canonical_start": selector.get("canonical_start"),
        "canonical_end": selector.get("canonical_end"),
        "proposition_fragment": str(selector["text"]),
        "supports_slot_ids": list(dict.fromkeys(supports)),
        "binds_proposition_slots": list(expected_slots),
        "proposition_slot_bindings": premise_bindings,
        "proposition_slot_spans": raw_spans,
        "event_id": str(selector.get("event_id") or ""),
        "object_tokens": list(selector.get("object_tokens") or []),
        "event_core_tokens": list(selector.get("event_core_tokens") or []),
        "predicate_match_kind": str(selector.get("predicate_match_kind") or ""),
        "local_relation_state": str(selector.get("local_relation_state") or ""),
        "relation_bearing": selector.get("relation_bearing") is True,
        "target_relation_present": selector.get("target_relation_present"),
        "meta_scope": selector.get("meta_scope"),
        "direct_relation_negated": selector.get("direct_relation_negated"),
        "candidate_relation_role": str(selector.get("candidate_relation_role") or ""),
        "semantic_alignment": alignment,
        "evidence_relation": header.relation,
        "canonical_evidence_plan_id": header.plan_id,
        "canonical_plan_digest": header.plan_digest,
        "frozen_projection_status": "validated",
    }


def _collect_projected_premises(
    refs: tuple[str, ...],
    projected: Sequence[_ProjectedPremise],
) -> _PlanPremises:
    return _PlanPremises(
        tuple(item.premise for item in projected),
        {ref: item.slot_evidence for ref, item in zip(refs, projected)},
        {
            f"P{index}": item.audit_slot_evidence
            for index, item in enumerate(projected, start=1)
        },
        {ref: item.covered_tokens for ref, item in zip(refs, projected)},
        {ref: item.alignment for ref, item in zip(refs, projected)},
    )


def _make_projection(
    header: _PlanHeader,
    events: _PlanEvents,
    projected: _PlanPremises,
    plan: Mapping[str, Any],
) -> FrozenCanonicalPropositionEvidencePlan:
    canonical = {
        "contract_id": FROZEN_CANONICAL_PROJECTION_CONTRACT,
        "plan_id": header.plan_id,
        "plan_digest": header.plan_digest,
        "polarity_relation": header.relation,
        "proof_mode": header.proof_mode,
        "span_refs": list(header.span_refs),
        "slot_refs": {slot: list(refs) for slot, refs in header.slot_refs.items()},
        "required_slots": list(header.expected_slots),
        "required_object_tokens": list(header.required_tokens),
        "covered_object_tokens": list(header.covered_tokens),
        "event_binding_id": events.event_binding_id,
        "event_subplans": deepcopy(list(events.event_subplans)),
        "comparison_relation": deepcopy(plan.get("comparison_relation")),
        "premises": deepcopy(list(projected.premises)),
        "slot_evidence": deepcopy(projected.slot_evidence),
        "audit_slot_evidence": deepcopy(projected.audit_slot_evidence),
        "covered_tokens_by_ref": {
            ref: list(tokens) for ref, tokens in projected.covered_tokens_by_ref.items()
        },
        "semantic_alignment_by_ref": deepcopy(projected.semantic_alignment_by_ref),
    }
    projection_digest = canonical_projection_digest(canonical)
    premises = [deepcopy(premise) for premise in projected.premises]
    for premise in premises:
        premise["canonical_projection_digest"] = projection_digest
    return FrozenCanonicalPropositionEvidencePlan(
        plan_id=header.plan_id,
        plan_digest=header.plan_digest,
        polarity_relation=header.relation,
        proof_mode=header.proof_mode,
        span_refs=header.span_refs,
        slot_refs=header.slot_refs,
        required_slots=header.expected_slots,
        required_object_tokens=header.required_tokens,
        covered_object_tokens=header.covered_tokens,
        event_binding_id=events.event_binding_id,
        event_subplans=events.event_subplans,
        comparison_relation=deepcopy(plan.get("comparison_relation")),
        premises=tuple(premises),
        slot_evidence=deepcopy(projected.slot_evidence),
        audit_slot_evidence=deepcopy(projected.audit_slot_evidence),
        covered_tokens_by_ref=projected.covered_tokens_by_ref,
        semantic_alignment_by_ref=projected.semantic_alignment_by_ref,
    )


def frozen_canonical_plan_projection_from_bundle(
    bundle: Any,
    *,
    plan_id: str,
    proposition: QuestionProposition | None = None,
    expected_slots: Sequence[str] | None = None,
    expected_plan_digest: str = "",
    slot_support_by_ref: Mapping[str, Sequence[str]] | None = None,
) -> tuple[FrozenCanonicalPropositionEvidencePlan | None, str]:
    """Resolve one selected plan from the immutable QASPER pack."""

    raw = getattr(bundle, "metadata", {}).get(
        QASPER_CANONICAL_SEMANTIC_PACK_METADATA_KEY
    )
    if not isinstance(raw, Mapping):
        return None, "canonical_plan_projection_pack_missing"
    records = raw.get("records")
    binding = raw.get("proposition_binding")
    if not isinstance(records, list) or not isinstance(binding, Mapping):
        return None, "canonical_plan_projection_pack_invalid"
    selected = binding.get("canonical_evidence_plan")
    selected = selected if isinstance(selected, Mapping) else {}
    plan = _bundle_plan(selected, plan_id)
    if plan is None:
        return None, "canonical_plan_projection_plan_missing"
    return frozen_canonical_plan_projection_checked(
        plan,
        records,
        proposition=proposition,
        expected_slots=expected_slots,
        expected_plan_digest=expected_plan_digest,
        slot_support_by_ref=slot_support_by_ref,
    )


def _bundle_plan(
    selected: Mapping[str, Any],
    plan_id: str,
) -> Mapping[str, Any] | None:
    for candidate in (
        selected.get("support_plan"),
        selected.get("contradiction_plan"),
    ):
        if isinstance(candidate, Mapping) and str(
            candidate.get("plan_id") or ""
        ) == str(plan_id or ""):
            return candidate
    return None
