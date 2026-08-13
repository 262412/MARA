from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class VerifiedClaim:
    claim_id: str
    claim: str
    status: str
    supporting_evidence_ids: tuple[str, ...] = ()
    contradicting_evidence_ids: tuple[str, ...] = ()
    input_answer_polarity: str = ""
    canonical_answer_polarity: str = ""
    semantic_correction_applied: bool = False
    authority_status: str = ""
    authoritative_evidence_id: str = ""
    authoritative_evidence_ref: str = ""
    authoritative_span_id: str = ""
    authoritative_quote: str = ""
    authoritative_span_start: int | None = None
    authoritative_span_end: int | None = None
    authoritative_canonical_start: int | None = None
    authoritative_canonical_end: int | None = None
    actor: str = ""
    section_scope: str = ""
    relation: str = ""
    object: str = ""
    predicate_arguments: tuple[str, ...] = ()
    qualifier: str = ""
    quantifier: str = ""
    supporting_evidence_spans: tuple[dict[str, Any], ...] = ()
    contradicting_evidence_spans: tuple[dict[str, Any], ...] = ()
    authoritative_conflict: dict[str, Any] = field(default_factory=dict)
    verified_slot_state: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["supporting_evidence_ids"] = list(self.supporting_evidence_ids)
        payload["contradicting_evidence_ids"] = list(self.contradicting_evidence_ids)
        payload["predicate"] = self.relation
        payload["arguments"] = list(self.predicate_arguments)
        payload["scope"] = self.section_scope
        payload["supporting_evidence_spans"] = [
            dict(value) for value in self.supporting_evidence_spans
        ]
        payload["contradicting_evidence_spans"] = [
            dict(value) for value in self.contradicting_evidence_spans
        ]
        return payload


@dataclass(frozen=True)
class VerifyDecision:
    mode: str
    status: str
    reason: str
    action: str = "generate"
    claims: list[str] = field(default_factory=list)
    unsupported_claims: list[str] = field(default_factory=list)
    unknown_claims: list[str] = field(default_factory=list)
    verified_citations: list[str] = field(default_factory=list)
    claim_results: list[dict[str, Any]] = field(default_factory=list)
    input_answer_polarity: str = ""
    canonical_answer_polarity: str = ""
    semantic_correction_applied: bool = False
    boolean_authority_status: str = ""
    authoritative_evidence_id: str = ""
    authoritative_evidence_ref: str = ""
    authoritative_span_id: str = ""
    authoritative_quote: str = ""
    authoritative_span_start: int | None = None
    authoritative_span_end: int | None = None
    authoritative_canonical_start: int | None = None
    authoritative_canonical_end: int | None = None
    actor: str = ""
    section_scope: str = ""
    relation: str = ""
    object: str = ""
    predicate_arguments: tuple[str, ...] = ()
    qualifier: str = ""
    quantifier: str = ""
    verified_support_slot_ids: list[str] = field(default_factory=list)
    authoritative_conflict: dict[str, Any] = field(default_factory=dict)
    typed_authority: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["predicate"] = self.relation
        payload["arguments"] = list(self.predicate_arguments)
        payload["scope"] = self.section_scope
        return payload
