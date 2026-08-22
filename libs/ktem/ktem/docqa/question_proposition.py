from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Mapping

from .qasper_relation_frame import question_relation_frame

QUESTION_PROPOSITION_CONTRACT = "question_proposition.v1"
TYPED_CONCLUSION_CONTRACT = "typed_conclusion.v1"


@dataclass(frozen=True, slots=True)
class QuestionProposition:
    """Lossless typed identity for the proposition asked by a question."""

    surface: str
    actor: str
    predicate: str
    object_role: str
    object_type: str
    subject_surface: str
    object_surface: str
    scope: str
    qualifier: str
    quantifier: str
    modality: str
    negated: bool
    time_scope: str
    relation_kind: str
    contract_id: str = QUESTION_PROPOSITION_CONTRACT

    @property
    def proposition_id(self) -> str:
        return _payload_digest(self.as_dict(include_id=False))

    def as_dict(self, *, include_id: bool = True) -> dict[str, Any]:
        payload = asdict(self)
        if include_id:
            payload["proposition_id"] = self.proposition_id
        return payload


@dataclass(frozen=True, slots=True)
class TypedConclusion:
    """A polarity-bearing conclusion bound to one typed question."""

    proposition_id: str
    polarity: str
    actor: str
    predicate: str
    object_role: str
    object_type: str
    subject_surface: str
    object_surface: str
    scope: str
    qualifier: str
    quantifier: str
    modality: str
    negated: bool
    time_scope: str
    surface: str
    contract_id: str = TYPED_CONCLUSION_CONTRACT

    @property
    def conclusion_id(self) -> str:
        return _payload_digest(self.as_dict(include_id=False))

    def as_dict(self, *, include_id: bool = True) -> dict[str, Any]:
        payload = asdict(self)
        if include_id:
            payload["conclusion_id"] = self.conclusion_id
        return payload


def build_question_proposition(question: str) -> QuestionProposition:
    surface = " ".join(str(question or "").split())
    frame = question_relation_frame(surface)
    subject_surface, object_surface = _surface_arguments(surface, frame.predicate)
    actor = frame.actor
    if actor == "unknown" and _named_subject(subject_surface):
        actor = subject_surface
    return QuestionProposition(
        surface=surface,
        actor=actor,
        predicate=frame.predicate or "unspecified",
        object_role=frame.expected_object_role,
        object_type=frame.expected_object_type,
        subject_surface=subject_surface,
        object_surface=object_surface,
        scope=frame.scope,
        qualifier=frame.qualifier,
        quantifier=frame.quantifier,
        modality=_question_modality(surface),
        negated=bool(
            re.search(r"\b(?:no|not|never|without)\b|n't\b", surface, re.I)
        ),
        time_scope=_time_scope(surface),
        relation_kind=frame.relation_kind,
    )


def typed_conclusion(
    proposition: QuestionProposition,
    polarity: str,
) -> TypedConclusion:
    if polarity not in {"yes", "no"}:
        raise ValueError("A typed conclusion requires yes or no polarity.")
    return TypedConclusion(
        proposition_id=proposition.proposition_id,
        polarity=polarity,
        actor=proposition.actor,
        predicate=proposition.predicate,
        object_role=proposition.object_role,
        object_type=proposition.object_type,
        subject_surface=proposition.subject_surface,
        object_surface=proposition.object_surface,
        scope=proposition.scope,
        qualifier=proposition.qualifier,
        quantifier=proposition.quantifier,
        modality=proposition.modality,
        negated=proposition.negated,
        time_scope=proposition.time_scope,
        surface=proposition.surface,
    )


def validate_question_proposition(value: Any, question: str) -> str:
    expected = build_question_proposition(question).as_dict()
    if not isinstance(value, Mapping) or dict(value) != expected:
        return "question_proposition_binding_invalid"
    return ""


def validate_typed_conclusion(
    value: Any,
    proposition: QuestionProposition,
    polarity: str,
) -> str:
    expected = typed_conclusion(proposition, polarity).as_dict()
    if not isinstance(value, Mapping) or dict(value) != expected:
        return "typed_conclusion_binding_invalid"
    return ""


def _payload_digest(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _surface_arguments(question: str, predicate: str) -> tuple[str, str]:
    surface = question.strip().rstrip("?")
    predicate_words = str(predicate or "").replace("_", " ").split()
    if not predicate_words:
        return surface, ""
    match = re.search(
        r"\b" + r"\s+".join(re.escape(value) for value in predicate_words) + r"\w*\b",
        surface,
        flags=re.IGNORECASE,
    )
    if match is None:
        return surface, ""
    subject = surface[: match.start()]
    subject = re.sub(
        r"^\s*(?:do|does|did|is|are|was|were|has|have|had|can|could|may|might|must|should|would|will)\s+",
        "",
        subject,
        flags=re.IGNORECASE,
    ).strip()
    return subject, surface[match.end() :].strip()


def _question_modality(question: str) -> str:
    match = re.search(
        r"\b(can|could|may|might|must|should|would|will)\b",
        question,
        flags=re.IGNORECASE,
    )
    return match.group(1).casefold() if match else "asserted"


def _named_subject(value: str) -> bool:
    tokens = {
        token.casefold()
        for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", value)
    }
    return bool(
        tokens
        - {
            "a",
            "an",
            "any",
            "it",
            "there",
            "the",
            "this",
            "that",
            "these",
            "those",
        }
    )


def _time_scope(question: str) -> str:
    match = re.search(
        r"\b(?:before|after|during|since|until)\s+(?:the\s+)?"
        r"([A-Za-z0-9][A-Za-z0-9_-]*(?:\s+[A-Za-z0-9][A-Za-z0-9_-]*){0,3})",
        question,
        flags=re.IGNORECASE,
    )
    if match is None:
        match = re.search(
            r"\bin\s+(?:19|20)\d{2}\b|\bin\s+(?:spring|summer|autumn|fall|winter)\b",
            question,
            flags=re.IGNORECASE,
        )
    return " ".join(match.group(0).split()) if match else "unspecified"
