from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from typing import Any, Mapping

from .boolean_relations import best_performance_question_subject
from .qasper_relation_frame import question_relation_frame

QUESTION_PROPOSITION_CONTRACT = "question_proposition.v1"
QUESTION_PROPOSITION_RESOLUTION_CONTRACT = "question_proposition_resolution.v1"
TYPED_CONCLUSION_CONTRACT = "typed_conclusion.v1"
CANDIDATE_TYPED_CONCLUSION_CONTRACT = "candidate_typed_conclusion.v1"
PROPOSITION_EVIDENCE_SLOTS = ("actor", "predicate", "object", "quantifier")

_EMPTY_OBJECT_SURFACES = {
    "",
    "at",
    "by",
    "for",
    "from",
    "in",
    "of",
    "on",
    "to",
    "with",
}
_FRONT_AUXILIARY = re.compile(
    r"^\s*(?:do|does|did|can|could|may|might|must|should|would|will|"
    r"has|have|had|is|are|was|were)\s+",
    re.IGNORECASE,
)
_REPAIR_RELATIONS: tuple[tuple[str, str], ...] = (
    ("be_subject_to", r"\bsubject(?:ed)?\s+to\b"),
    ("be_collection_of", r"\b(?:a\s+)?collection\s+of\b"),
    ("focus_on", r"\bfocus(?:es|ed|ing)?\s+on\b"),
    (
        "cause",
        r"\b(?:result(?:s|ed|ing)?\s+in|lead(?:s|ing)?\s+to|caus(?:e|es|ed|ing))\b",
    ),
    ("inspect", r"\binspect(?:s|ed|ing)?\b"),
    ("associate", r"\bassociat(?:e|es|ed|ing)\b"),
    ("annotate", r"\bannotat(?:e|es|ed|ing)\b"),
    ("add", r"\badd(?:s|ed|ing)?\b"),
    ("have", r"\b(?:have|has|had)\b"),
    ("help", r"\bhelp(?:s|ed|ing)?\b"),
    ("collect", r"\bcollect(?:s|ed|ing)?\b"),
    ("compare", r"\bcompar(?:e|es|ed|ing)\b"),
    (
        "evaluate",
        r"\b(?:evaluat(?:e|es|ed|ing)|assess(?:es|ed|ing)?|"
        r"experiment(?:ed|ing)|experiment\s+with)\b",
    ),
    ("use", r"\b(?:use|uses|used|using)\b"),
    ("train", r"\btrain(?:s|ed|ing)?\b"),
    ("improve", r"\bimprov(?:e|es|ed|ing|ement)\b"),
)


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


@dataclass(frozen=True, slots=True)
class QuestionPropositionResolution:
    """Pre-audit resolution of one question into a complete proposition."""

    initial: QuestionProposition
    proposition: QuestionProposition
    status: str
    reason: str
    repair_kind: str
    contract_id: str = QUESTION_PROPOSITION_RESOLUTION_CONTRACT

    def as_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "status": self.status,
            "reason": self.reason,
            "repair_kind": self.repair_kind,
            "initial": self.initial.as_dict(),
            "proposition": self.proposition.as_dict(),
        }


def applicable_proposition_evidence_slots(
    proposition: QuestionProposition,
) -> tuple[str, ...]:
    """Return slots that require evidence for this concrete proposition."""

    return tuple(
        slot
        for slot in PROPOSITION_EVIDENCE_SLOTS
        if not (slot == "quantifier" and proposition.quantifier == "none")
    )


def not_applicable_proposition_evidence_slots(
    proposition: QuestionProposition,
) -> tuple[str, ...]:
    applicable = set(applicable_proposition_evidence_slots(proposition))
    return tuple(slot for slot in PROPOSITION_EVIDENCE_SLOTS if slot not in applicable)


def build_question_proposition(question: str) -> QuestionProposition:
    return resolve_question_proposition(question).proposition


def resolve_question_proposition(question: str) -> QuestionPropositionResolution:
    initial = _initial_question_proposition(question)
    reason = question_proposition_completeness_reason(initial)
    if not reason:
        return QuestionPropositionResolution(
            initial=initial,
            proposition=initial,
            status="complete",
            reason="",
            repair_kind="none",
        )
    repaired = _repair_main_clause(initial)
    repaired_reason = question_proposition_completeness_reason(repaired)
    return QuestionPropositionResolution(
        initial=initial,
        proposition=repaired,
        status="repaired" if not repaired_reason else "incomplete",
        reason=reason if not repaired_reason else repaired_reason,
        repair_kind="deterministic_main_clause" if not repaired_reason else "none",
    )


def question_proposition_completeness_reason(
    proposition: QuestionProposition,
) -> str:
    if proposition.predicate in {"", "unspecified"}:
        return "question_proposition_predicate_unspecified"
    if not proposition.subject_surface.strip():
        return "question_proposition_subject_missing"
    if proposition.object_surface.strip().casefold() in _EMPTY_OBJECT_SURFACES:
        return "question_proposition_object_missing"
    return ""


def _initial_question_proposition(question: str) -> QuestionProposition:
    surface = " ".join(str(question or "").split())
    frame = question_relation_frame(surface)
    subject_surface, object_surface = _surface_arguments(surface, frame.predicate)
    if ranking_subject := best_performance_question_subject(surface):
        subject_surface = ranking_subject
        object_surface = "best performance"
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
        negated=bool(re.search(r"\b(?:no|not|never|without)\b|n't\b", surface, re.I)),
        time_scope=_time_scope(surface),
        relation_kind=frame.relation_kind,
    )


def _repair_main_clause(initial: QuestionProposition) -> QuestionProposition:
    clause = initial.surface.strip().rstrip("?")
    clause = _FRONT_AUXILIARY.sub("", clause, count=1).strip()
    matches = [
        (match.start(), match.end(), predicate)
        for predicate, pattern in _REPAIR_RELATIONS
        if (match := re.search(pattern, clause, flags=re.IGNORECASE)) is not None
    ]
    if not matches:
        return initial
    start, end, predicate = min(matches, key=lambda value: (value[0], value[1]))
    subject = clause[:start].strip(" ,")
    object_surface = clause[end:].strip(" ,")
    if not object_surface and start > 0:
        subject, object_surface = _passive_arguments(subject)
    if not subject or not object_surface:
        return initial
    actor = initial.actor
    if actor not in {"current_paper", "prior_work"}:
        actor = subject if _named_subject(subject) else "unknown"
    return replace(
        initial,
        actor=actor,
        predicate=predicate,
        subject_surface=subject,
        object_surface=object_surface,
        object_role="cause" if predicate == "cause" else "object",
        relation_kind="cause" if predicate == "cause" else "attribute",
    )


def _passive_arguments(value: str) -> tuple[str, str]:
    match = re.match(
        r"(?P<subject>(?:the|a|an|this|that|these|those)\s+\S+)\s+" r"(?P<object>.+)",
        value,
        flags=re.IGNORECASE,
    )
    if match is None:
        return value, ""
    return match.group("subject").strip(), match.group("object").strip()


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


def candidate_typed_conclusion(
    proposition: QuestionProposition,
    candidate: str,
) -> dict[str, Any]:
    """Bind the original Boolean candidate to the canonical proposition."""

    normalized = str(candidate or "").strip().casefold()
    if normalized in {"yes", "no"}:
        return typed_conclusion(proposition, normalized).as_dict()
    if normalized != "unanswerable":
        return {}
    payload = {
        "contract_id": CANDIDATE_TYPED_CONCLUSION_CONTRACT,
        "proposition_id": proposition.proposition_id,
        "polarity": "unanswerable",
        "actor": proposition.actor,
        "predicate": proposition.predicate,
        "object_role": proposition.object_role,
        "object_type": proposition.object_type,
        "subject_surface": proposition.subject_surface,
        "object_surface": proposition.object_surface,
        "scope": proposition.scope,
        "qualifier": proposition.qualifier,
        "quantifier": proposition.quantifier,
        "modality": proposition.modality,
        "negated": proposition.negated,
        "time_scope": proposition.time_scope,
        "surface": proposition.surface,
    }
    payload["conclusion_id"] = _payload_digest(payload)
    return payload


def proposition_evidence_bindings(
    proposition: QuestionProposition,
) -> dict[str, str]:
    """Return the canonical evidence-bound fields for one proposition."""

    return {
        "actor": proposition.actor,
        "predicate": proposition.predicate,
        "object": proposition.object_surface,
        "quantifier": proposition.quantifier,
    }


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


def validate_candidate_typed_conclusion(
    value: Any,
    proposition: QuestionProposition,
    candidate: str,
) -> str:
    expected = candidate_typed_conclusion(proposition, candidate)
    if not expected or not isinstance(value, Mapping) or dict(value) != expected:
        return "candidate_typed_conclusion_binding_invalid"
    return ""


def _payload_digest(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _surface_arguments(question: str, predicate: str) -> tuple[str, str]:
    surface = question.strip().rstrip("?")
    predicate_words = str(predicate or "").replace("_", " ").split()
    if not predicate_words:
        return surface, ""
    predicate_pattern = (
        r"\b" + r"\s+".join(re.escape(value) for value in predicate_words) + r"\w*\b"
    )
    fronted_match = re.match(
        r"^\s*(?:what|which)\s+(?P<object>.+?)\s+"
        r"(?:do|does|did|can|could|may|might|must|should|would|will|"
        r"has|have|had|is|are|was|were)\s+"
        r"(?P<subject>.+?)\s+" + predicate_pattern + r"\s*$",
        surface,
        flags=re.IGNORECASE,
    )
    if fronted_match is not None:
        subject = fronted_match.group("subject").strip()
        object_surface = fronted_match.group("object").strip(" ,")
        if subject and object_surface:
            return subject, object_surface
    match = re.search(predicate_pattern, surface, flags=re.IGNORECASE)
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
        token.casefold() for token in re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", value)
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
