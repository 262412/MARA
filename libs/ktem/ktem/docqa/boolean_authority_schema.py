from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class BooleanEvidenceAuthority:
    evidence_id: str
    evidence_ref: str
    span_id: str
    quote: str
    span_start: int
    span_end: int
    canonical_start: int | None
    canonical_end: int | None
    actor: str
    section_scope: str
    relation: str
    object: str
    quantifier: str
    polarity: str
    reason: str
    qualifier: str = "none"
    source_id: str = ""
    page_label: str = ""

    @property
    def predicate(self) -> str:
        return self.relation

    @property
    def scope(self) -> str:
        return self.section_scope

    @property
    def arguments(self) -> tuple[str, ...]:
        return (self.object,) if self.object else ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "evidence_ref": self.evidence_ref,
            "span_id": self.span_id,
            "quote": self.quote,
            "span_start": self.span_start,
            "span_end": self.span_end,
            "canonical_start": self.canonical_start,
            "canonical_end": self.canonical_end,
            "actor": self.actor,
            "predicate": self.predicate,
            "section_scope": self.section_scope,
            "scope": self.scope,
            "relation": self.relation,
            "object": self.object,
            "arguments": list(self.arguments),
            "quantifier": self.quantifier,
            "polarity": self.polarity,
            "qualifier": self.qualifier,
            "reason": self.reason,
            "source_id": self.source_id,
            "page_label": self.page_label,
        }


@dataclass(frozen=True)
class BooleanClaimAuthority:
    claim: str
    status: str
    input_answer_polarity: str
    canonical_answer_polarity: str
    semantic_correction_applied: bool
    supporting: tuple[BooleanEvidenceAuthority, ...] = ()
    contradicting: tuple[BooleanEvidenceAuthority, ...] = ()
    reason: str = ""
    authoritative_conflict: dict[str, Any] | None = None
