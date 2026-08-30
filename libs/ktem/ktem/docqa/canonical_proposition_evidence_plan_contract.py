from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from typing import Any

from .question_proposition import QuestionProposition

CANONICAL_PROPOSITION_EVIDENCE_PLAN_CONTRACT = "canonical_proposition_evidence_plan.v2"
CANONICAL_EVENT_PROPOSITION_PLAN_CONTRACT = "canonical_event_proposition_plan.v1"
CANONICAL_EVENT_COMPARISON_RELATION_CONTRACT = "canonical_event_comparison_relation.v1"

RELATION_BOUND_SUPPORT = "relation_bound_support"
RELATION_BOUND_CONTRADICTION = "relation_bound_contradiction"
AMBIGUOUS_CONFLICT = "ambiguous_conflict"
UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class CanonicalEventPropositionPlan:
    event_id: str
    event_binding_id: str
    span_refs: tuple[str, ...]
    slot_refs: tuple[tuple[str, tuple[str, ...]], ...]
    required_object_tokens: tuple[str, ...]
    covered_object_tokens: tuple[str, ...]
    contract_id: str = CANONICAL_EVENT_PROPOSITION_PLAN_CONTRACT

    def as_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "event_id": self.event_id,
            "event_binding_id": self.event_binding_id,
            "span_refs": list(self.span_refs),
            "slot_refs": {slot: list(refs) for slot, refs in self.slot_refs},
            "required_object_tokens": list(self.required_object_tokens),
            "covered_object_tokens": list(self.covered_object_tokens),
        }


@dataclass(frozen=True, slots=True)
class CanonicalEventComparisonRelation:
    relation_type: str
    contradicting_event_binding_id: str
    reference_event_binding_id: str
    contract_id: str = CANONICAL_EVENT_COMPARISON_RELATION_CONTRACT

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CanonicalEvidenceSetPlan:
    plan_id: str
    event_binding_id: str
    polarity_relation: str
    span_refs: tuple[str, ...]
    slot_refs: tuple[tuple[str, tuple[str, ...]], ...]
    required_object_tokens: tuple[str, ...]
    covered_object_tokens: tuple[str, ...]
    event_subplans: tuple[CanonicalEventPropositionPlan, ...]
    comparison_relation: CanonicalEventComparisonRelation | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "event_binding_id": self.event_binding_id,
            "polarity_relation": self.polarity_relation,
            "span_refs": list(self.span_refs),
            "slot_refs": {slot: list(refs) for slot, refs in self.slot_refs},
            "required_object_tokens": list(self.required_object_tokens),
            "covered_object_tokens": list(self.covered_object_tokens),
            "event_subplans": [value.as_dict() for value in self.event_subplans],
            "comparison_relation": (
                self.comparison_relation.as_dict()
                if self.comparison_relation is not None
                else None
            ),
        }


@dataclass(frozen=True, slots=True)
class CanonicalPropositionEvidencePlan:
    proposition_id: str
    candidate_transaction_id: str
    event_binding_id: str
    span_refs: tuple[str, ...]
    slot_refs: tuple[tuple[str, tuple[str, ...]], ...]
    required_object_tokens: tuple[str, ...]
    covered_object_tokens: tuple[str, ...]
    polarity_relation: str
    binding_state: str
    span_universe_digest: str
    support_plan: CanonicalEvidenceSetPlan | None
    contradiction_plan: CanonicalEvidenceSetPlan | None
    contract_id: str = CANONICAL_PROPOSITION_EVIDENCE_PLAN_CONTRACT

    @property
    def plan_digest(self) -> str:
        return canonical_plan_digest(self._payload())

    @property
    def plan_id(self) -> str:
        return self.plan_digest

    def _payload(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["support_plan"] = (
            self.support_plan.as_dict() if self.support_plan is not None else None
        )
        payload["contradiction_plan"] = (
            self.contradiction_plan.as_dict()
            if self.contradiction_plan is not None
            else None
        )
        return payload

    def as_dict(self) -> dict[str, Any]:
        return {
            **self._payload(),
            "span_refs": list(self.span_refs),
            "slot_refs": {slot: list(refs) for slot, refs in self.slot_refs},
            "required_object_tokens": list(self.required_object_tokens),
            "covered_object_tokens": list(self.covered_object_tokens),
            "plan_id": self.plan_id,
            "plan_digest": self.plan_digest,
            "immutable": True,
        }


@dataclass(frozen=True, slots=True)
class CanonicalPropositionEvidenceSelection:
    plan: CanonicalPropositionEvidencePlan
    support: tuple[dict[str, Any], ...] | None
    contradiction: tuple[dict[str, Any], ...] | None
    construction_trace: dict[str, Any]


def canonical_selector_sort_key(
    value: Mapping[str, Any],
) -> tuple[str, int, int, str]:
    return (
        str(value.get("evidence_id") or ""),
        int(value.get("span_start") or 0),
        int(value.get("span_end") or 0),
        str(value.get("selector_id") or ""),
    )


def canonical_event_identity(
    evidence_id: str,
    event_start: int,
    event_end: int,
    event_text: str,
) -> str:
    return canonical_plan_digest(
        {
            "evidence_id": str(evidence_id or ""),
            "event_start": int(event_start),
            "event_end": int(event_end),
            "event_text": str(event_text or ""),
        }
    )


def canonical_predicate_match_kind(
    proposition: QuestionProposition,
    predicate_text: str,
) -> str:
    observed = {
        _predicate_surface_root(token)
        for token in str(predicate_text or "").casefold().split()
    }
    target = {
        _predicate_surface_root(token)
        for token in str(proposition.predicate or "").replace("_", " ").split()
        if token not in {"be", "of", "on", "to"}
    }
    return "exact" if target and target & observed else "alias"


def canonical_plan_evidence_sets(
    plan: Mapping[str, Any],
) -> dict[str, tuple[str, ...]]:
    output: dict[str, tuple[str, ...]] = {}
    for key in ("support_plan", "contradiction_plan"):
        raw = plan.get(key)
        if not isinstance(raw, Mapping):
            continue
        plan_id = str(raw.get("plan_id") or "")
        refs = tuple(str(value) for value in raw.get("span_refs") or [] if value)
        if plan_id and refs:
            output[plan_id] = refs
    return output


def canonical_plan_digest(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def canonical_span_universe_digest(
    selectors: Sequence[Mapping[str, Any]],
) -> str:
    return canonical_plan_digest(
        [
            {
                "evidence_id": str(selector.get("evidence_id") or ""),
                "selector_id": str(selector.get("selector_id") or ""),
                "span_start": int(selector.get("span_start") or 0),
                "span_end": int(selector.get("span_end") or 0),
                "text": str(selector.get("text") or ""),
                "event_id": str(selector.get("event_id") or ""),
            }
            for selector in selectors
        ]
    )


def canonical_selector_spans_overlap(
    selectors: Sequence[Mapping[str, Any]],
) -> bool:
    previous_evidence_id = ""
    previous_end = -1
    for selector in selectors:
        evidence_id = str(selector.get("evidence_id") or "")
        if evidence_id != previous_evidence_id:
            previous_evidence_id = evidence_id
            previous_end = -1
        start = int(selector.get("span_start") or 0)
        end = int(selector.get("span_end") or 0)
        if start < previous_end:
            return True
        previous_end = end
    return False


def _predicate_surface_root(value: str) -> str:
    token = str(value or "").casefold().strip(".,;:!?()[]{}\"'")
    if token.endswith("ied") and len(token) > 4:
        return token[:-3] + "y"
    for suffix in ("ing", "ed", "es", "s"):
        if token.endswith(suffix) and len(token) > len(suffix) + 2:
            token = token[: -len(suffix)]
            break
    return token[:-1] if token.endswith("e") and len(token) > 4 else token
