from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any

from .boolean_proposition_polarity import _target_relation_polarity
from .boolean_relations import primary_boolean_relation
from .question_proposition import build_question_proposition
from .semantic_relation_clause_lexical import (
    clause_spans,
    direct_relation_negated,
    predicate_spans,
    semantic_content_token_set,
)

QASPER_BOOLEAN_NO_EVIDENCE_CONTRACT = "qasper_boolean_no_evidence.v1"

_LIMITED_SCOPE_RE = re.compile(
    r"\b(?:only|merely|initial|sampled?|subset|partial(?:ly)?|limited)\b",
    re.IGNORECASE,
)
_VALIDATION_RE = re.compile(
    r"\b(?:check|control|quality|validat|verif)\w*\b",
    re.IGNORECASE,
)
_INCOMPLETE_SCOPE_RE = re.compile(
    r"\b(?:future\s+work|remain(?:s|ed)?|not\s+(?:fully\s+)?validat|"
    r"hard(?:er)?\s+to\s+validat|without\s+(?:full\s+)?validat)\w*\b",
    re.IGNORECASE,
)
_EXTERNAL_PROVENANCE_RE = re.compile(
    r"\b(?:came|comes|obtained|sourced|provided|supplied)\s+from\b"
    r"[^.!?;]{0,100}\b(?:existing|external|public|prior|third[- ]party)\b|"
    r"\b(?:existing|external|prior|third[- ]party)\b[^.!?;]{0,80}"
    r"\b(?:source|dataset|corpus|resource)\b|"
    r"\bprivately[- ]owned\b",
    re.IGNORECASE,
)
_TRAINING_TARGET_RE = re.compile(
    r"\b(?:classifier|classifiers|model|models)\b[^.!?;]{0,80}"
    r"\btrain\w*\b[^.!?;]{0,24}\bon\b",
    re.IGNORECASE,
)
_TRAINING_INPUT_RE = re.compile(
    r"\b(?:train\w*\s+"
    r"(?:(?:a\s+series\s+of|a|the|our|one|two|three|four|five|several|multiple)\s+)?"
    r"(?:classifier|classifiers|model|models)|"
    r"(?:classifier|classifiers|model|models)\s+(?:is|are|was|were)\s+train\w*)"
    r"[^.!?;]{0,48}\bon\s+(?P<object>[^.!?;]{2,120})",
    re.IGNORECASE,
)


def qasper_no_evidence_set_analysis(
    question: str,
    spans: Sequence[str | Mapping[str, Any]],
) -> dict[str, Any]:
    """Classify evidence that may justify a QASPER Boolean ``no``.

    Missing mentions remain inadmissible.  In addition to literal relation
    negation, the contract admits locally visible mutually exclusive role or
    value bindings and an explicitly restricted validation scope.  These are
    contradictions of the typed proposition, not closed-world guesses.
    """

    texts = [_span_text(value) for value in spans]
    texts = [value for value in texts if value]
    joined = "\n".join(texts)
    proposition = build_question_proposition(question)
    classification = "absence_only"
    reason = "no_auditable_support_or_contradiction"
    admissible = False

    if any(_relation_explicitly_negated(question, text) for text in texts):
        classification = "explicit_negation"
        reason = "target_relation_explicitly_negated"
        admissible = True
    elif _explicit_partial_scope_contradiction(question, joined):
        classification = "partial_scope_only"
        reason = "evidence_explicitly_limits_relation_to_a_subset"
        admissible = True
    elif _role_incompatibility(question, joined):
        classification = "role_incompatibility"
        reason = "evidence_binds_a_required_role_to_an_incompatible_alternative"
        admissible = True

    payload = {
        "contract_id": QASPER_BOOLEAN_NO_EVIDENCE_CONTRACT,
        "classification": classification,
        "reason": reason,
        "admissible_as_explicit_contradiction": admissible,
        "closed_world_inference_required": not admissible,
        "annotation_contract_status": (
            "auditable_no" if admissible else "ambiguous_no_evidence_semantics"
        ),
        "question_digest": _digest(question.strip()),
        "evidence_span_digests": [_digest(text) for text in texts],
        "proposition_actor": proposition.actor,
        "proposition_predicate": proposition.predicate,
        "proposition_object": proposition.object_surface,
        "proposition_quantifier": proposition.quantifier,
    }
    payload["analysis_digest"] = _digest(payload)
    return payload


def qasper_support_evidence_binding_complete(
    question: str,
    spans: Sequence[str | Mapping[str, Any]],
) -> bool:
    """Reject positive bindings that retain unresolved role or scope gaps."""

    texts = [_span_text(value) for value in spans]
    joined = "\n".join(texts)
    relation = primary_boolean_relation(question)
    if (
        relation in {"validate", "attribute"}
        or "quality control" in question.casefold()
    ) and _INCOMPLETE_SCOPE_RE.search(joined):
        return False
    if not _TRAINING_TARGET_RE.search(question):
        return True
    proposition = build_question_proposition(question)
    expected = semantic_content_token_set(proposition.object_surface) - {
        "classifier",
        "model",
        "train",
    }
    expected.update(semantic_content_token_set(proposition.subject_surface))
    for text in texts:
        for match in _TRAINING_INPUT_RE.finditer(text):
            actual = semantic_content_token_set(match.group("object"))
            if actual & expected:
                return True
    return False


def _explicit_partial_scope_contradiction(question: str, evidence: str) -> bool:
    relation = primary_boolean_relation(question)
    if relation not in {"validate", "attribute"} and "quality control" not in (
        question.casefold()
    ):
        return False
    if not _VALIDATION_RE.search(evidence):
        return False
    for validation in _VALIDATION_RE.finditer(evidence):
        window = evidence[max(0, validation.start() - 120) : validation.end() + 160]
        if _LIMITED_SCOPE_RE.search(window):
            return True
    return False


def _relation_explicitly_negated(question: str, text: str) -> bool:
    if _target_relation_polarity(question, text) is True:
        return True
    proposition = build_question_proposition(question)
    for clause_start, clause_end in clause_spans(text):
        clause = text[clause_start:clause_end]
        for span in predicate_spans(
            clause,
            proposition.predicate,
            offset=clause_start,
        ):
            local_start = int(span.get("span_start") or 0) - clause_start
            if direct_relation_negated(clause, local_start) is True:
                return True
    return False


def _role_incompatibility(question: str, evidence: str) -> bool:
    relation = primary_boolean_relation(question)
    proposition = build_question_proposition(question)
    if relation == "create" and proposition.actor == "current_paper":
        has_relation = re.search(
            r"\b(?:collect|collected|gather|gathered|create|created|build|built)\w*\b",
            evidence,
            re.IGNORECASE,
        )
        has_scope = bool(
            proposition.quantifier not in {"", "none"}
            and re.search(
                rf"\b{re.escape(str(proposition.quantifier))}\b",
                evidence,
                re.IGNORECASE,
            )
        )
        if has_relation and has_scope and _EXTERNAL_PROVENANCE_RE.search(evidence):
            return True
    if not _TRAINING_TARGET_RE.search(question):
        return False
    expected = semantic_content_token_set(proposition.object_surface) - {
        "classifier",
        "model",
        "train",
    }
    subject = semantic_content_token_set(proposition.subject_surface)
    if not expected or not (subject & semantic_content_token_set(evidence)):
        return False
    for match in _TRAINING_INPUT_RE.finditer(evidence):
        actual = semantic_content_token_set(match.group("object"))
        if actual and not (actual & expected):
            return True
    return False


def _span_text(value: str | Mapping[str, Any]) -> str:
    if isinstance(value, Mapping):
        return str(value.get("text") or value.get("quote") or "").strip()
    return str(value or "").strip()


def _digest(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
