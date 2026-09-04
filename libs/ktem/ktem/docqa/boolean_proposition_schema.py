from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .boolean_authority_schema import BooleanAuthorityState, candidate_authority_state
from .evidence_identity import identity_of


@dataclass(frozen=True)
class BooleanProposition:
    actor: str
    action: str
    object: str
    section_scope: str
    polarity: str
    quantifier: str
    qualifier: str = "none"

    @property
    def predicate(self) -> str:
        return self.action

    @property
    def scope(self) -> str:
        return self.section_scope

    @property
    def arguments(self) -> tuple[str, ...]:
        return (self.object,) if self.object else ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "actor": self.actor,
            "predicate": self.predicate,
            "relation": self.action,
            "action": self.action,
            "object": self.object,
            "arguments": list(self.arguments),
            "polarity": self.polarity,
            "qualifier": self.qualifier,
            "quantifier": self.quantifier,
            "scope": self.scope,
            "section_scope": self.section_scope,
        }

    @property
    def key(self) -> tuple[str, str, str, str, str, str, str]:
        return (
            self.actor,
            self.action,
            self.object,
            self.section_scope,
            self.quantifier,
            self.qualifier,
            self.polarity,
        )

    @property
    def claim_key(self) -> tuple[str, str, str, str, str, str]:
        return self.key[:-1]


@dataclass(frozen=True)
class BooleanEvidenceAssessment:
    item: dict[str, Any]
    classification: str
    proposition: BooleanProposition
    relation_score: float
    object_score: float
    reason: str
    span_id: str = ""
    span_text: str = ""
    actor_score: float = 0.0
    scope_score: float = 0.0
    candidate_relevance: bool = False

    @property
    def evidence_id(self) -> str:
        return identity_of(self.item).key

    @property
    def authority_state(self) -> BooleanAuthorityState:
        return candidate_authority_state(self.candidate_relevance)

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.proposition.as_dict(),
            "evidence_id": self.evidence_id,
            "span_id": self.span_id,
            "exact_span": self.span_text,
            "classification": self.classification,
            "relation_score": self.relation_score,
            "object_score": self.object_score,
            "actor_score": self.actor_score,
            "scope_score": self.scope_score,
            "candidate_relevance": self.candidate_relevance,
            "authority_state": self.authority_state,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class BooleanEvidenceSet:
    supports: tuple[BooleanEvidenceAssessment, ...]
    contradicts: tuple[BooleanEvidenceAssessment, ...]
    unrelated: tuple[BooleanEvidenceAssessment, ...]
    insufficient_scope: tuple[BooleanEvidenceAssessment, ...]
