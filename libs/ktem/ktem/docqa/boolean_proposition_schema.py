from __future__ import annotations

from dataclasses import dataclass
from typing import Any


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


@dataclass(frozen=True)
class BooleanEvidenceSet:
    supports: tuple[BooleanEvidenceAssessment, ...]
    contradicts: tuple[BooleanEvidenceAssessment, ...]
    unrelated: tuple[BooleanEvidenceAssessment, ...]
    insufficient_scope: tuple[BooleanEvidenceAssessment, ...]
