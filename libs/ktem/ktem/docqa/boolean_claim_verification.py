from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .boolean_evidence_scope import (
    ClosedScopeResolution,
    evidence_item_text,
    resolve_closed_scope_boolean,
)
from .boolean_proposition_context import (
    PropositionContextWindow,
    exact_proposition_context,
)
from .boolean_proposition_evidence import (
    BooleanEvidenceAssessment,
    classify_boolean_evidence_set,
)
from .boolean_relations import boolean_relation_lemmas, primary_boolean_relation
from .evidence_identity import identity_of
from .evidence_text import extract_final_answer_text


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
            "section_scope": self.section_scope,
            "relation": self.relation,
            "object": self.object,
            "quantifier": self.quantifier,
            "polarity": self.polarity,
            "reason": self.reason,
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


def canonical_boolean_answer_polarity(answer: str) -> str:
    text = extract_final_answer_text(answer).strip().lower()
    explicit = list(re.finditer(r"\banswer\s*:\s*(yes|true|no|false)\b", text))
    if explicit:
        return _normalized_polarity(explicit[-1].group(1))
    match = re.match(
        r"^(?:overall\s*[,;:]?\s*)?(yes|true|no|false)\b",
        text,
    )
    return _normalized_polarity(match.group(1)) if match else ""


def boolean_claim_authority(
    prompt: str,
    answer: str,
    evidence_items: list[dict[str, Any]],
) -> BooleanClaimAuthority | None:
    input_polarity = canonical_boolean_answer_polarity(answer)
    if not input_polarity:
        return None
    closed_scope = resolve_closed_scope_boolean(prompt, evidence_items)
    resolved = _authority_from_closed_scope(prompt, closed_scope)
    if resolved is None:
        resolved = _non_english_result_authority(prompt, evidence_items)
    if resolved is None:
        resolved = _exclusive_requirement_authority(prompt, evidence_items)
    if resolved is not None:
        canonical_polarity, authority = resolved
        return _supported_authority(
            prompt,
            input_polarity,
            canonical_polarity,
            (authority,),
            reason="exact_closed_scope_proposition",
        )

    classified = classify_boolean_evidence_set(prompt, input_polarity, evidence_items)
    supporting = _exact_authorities(prompt, classified.supports)
    contradicting = _exact_authorities(prompt, classified.contradicts)
    if supporting and contradicting:
        return BooleanClaimAuthority(
            claim=f"{input_polarity}: {prompt}",
            status="conflicting",
            input_answer_polarity=input_polarity,
            canonical_answer_polarity="",
            semantic_correction_applied=False,
            supporting=supporting,
            contradicting=contradicting,
            reason="conflicting_exact_boolean_propositions",
        )
    if supporting:
        return _supported_authority(
            prompt,
            input_polarity,
            input_polarity,
            supporting,
            reason="exact_boolean_proposition",
        )
    if contradicting:
        canonical_polarity = "no" if input_polarity == "yes" else "yes"
        return _supported_authority(
            prompt,
            input_polarity,
            canonical_polarity,
            contradicting,
            contradicting=(),
            reason="exact_opposite_boolean_proposition",
        )
    return BooleanClaimAuthority(
        claim=f"{input_polarity}: {prompt}",
        status="unknown",
        input_answer_polarity=input_polarity,
        canonical_answer_polarity="",
        semantic_correction_applied=False,
        reason="no_exact_boolean_authority",
    )


def boolean_evidence_assessment(
    prompt: str,
    answer: str,
    evidence_items: list[dict[str, Any]],
) -> tuple[str, str, tuple[str, ...], tuple[str, ...]] | None:
    """Compatibility projection of the exact Boolean authority assessment."""

    assessment = boolean_claim_authority(prompt, answer, evidence_items)
    if assessment is None:
        return None
    return (
        assessment.claim,
        assessment.status,
        tuple(value.evidence_id for value in assessment.supporting),
        tuple(value.evidence_id for value in assessment.contradicting),
    )


def _supported_authority(
    prompt: str,
    input_polarity: str,
    canonical_polarity: str,
    supporting: tuple[BooleanEvidenceAuthority, ...],
    *,
    contradicting: tuple[BooleanEvidenceAuthority, ...] = (),
    reason: str,
) -> BooleanClaimAuthority:
    return BooleanClaimAuthority(
        claim=f"{canonical_polarity}: {prompt}",
        status="supported",
        input_answer_polarity=input_polarity,
        canonical_answer_polarity=canonical_polarity,
        semantic_correction_applied=input_polarity != canonical_polarity,
        supporting=supporting,
        contradicting=contradicting,
        reason=reason,
    )


def _authority_from_closed_scope(
    prompt: str,
    resolution: ClosedScopeResolution | None,
) -> tuple[str, BooleanEvidenceAuthority] | None:
    if resolution is None:
        return None
    item = resolution.evidence_item
    window = _exact_window(item, resolution.evidence_quote)
    if window is None:
        return None
    identity = identity_of(item).key
    span_id = _span_identity(identity, window)
    return (
        resolution.polarity,
        BooleanEvidenceAuthority(
            evidence_id=identity,
            evidence_ref=span_id,
            span_id=span_id,
            quote=window.text,
            span_start=window.start,
            span_end=window.end,
            canonical_start=window.canonical_start,
            canonical_end=window.canonical_end,
            actor=resolution.decision.actor,
            section_scope=resolution.decision.section_role,
            relation=primary_boolean_relation(prompt),
            object="",
            quantifier=resolution.decision.quantifier,
            polarity=resolution.polarity,
            reason=resolution.decision.reason,
        ),
    )


def _exclusive_requirement_authority(
    prompt: str,
    evidence_items: list[dict[str, Any]],
) -> tuple[str, BooleanEvidenceAuthority] | None:
    question_terms = _required_object_terms(prompt)
    if not question_terms:
        return None
    candidates: list[BooleanEvidenceAuthority] = []
    for item in evidence_items:
        text = evidence_item_text(item)
        for match in re.finditer(
            r"[^.!?\n]*(?:only|sole)\s+requirement\s+(?:is|was|are)\s+[^.!?\n]+[.!?]?",
            text,
            flags=re.IGNORECASE,
        ):
            quote = match.group(0).strip()
            window = _exact_window(item, quote)
            if window is None:
                continue
            requirement_terms = _semantic_terms(quote)
            asked_object_present = question_terms <= requirement_terms
            polarity = "yes" if asked_object_present else "no"
            identity = identity_of(item).key
            span_id = _span_identity(identity, window)
            candidates.append(
                BooleanEvidenceAuthority(
                    evidence_id=identity,
                    evidence_ref=span_id,
                    span_id=span_id,
                    quote=window.text,
                    span_start=window.start,
                    span_end=window.end,
                    canonical_start=window.canonical_start,
                    canonical_end=window.canonical_end,
                    actor="current_paper",
                    section_scope="document",
                    relation="require",
                    object=" ".join(sorted(requirement_terms)),
                    quantifier="only",
                    polarity=polarity,
                    reason="explicit_exclusive_requirement",
                )
            )
    polarities = {candidate.polarity for candidate in candidates}
    if len(polarities) != 1 or not candidates:
        return None
    return candidates[0].polarity, _best_authority(tuple(candidates))


def _exact_authorities(
    prompt: str,
    assessments: tuple[BooleanEvidenceAssessment, ...],
) -> tuple[BooleanEvidenceAuthority, ...]:
    authorities: list[BooleanEvidenceAuthority] = []
    for assessment in assessments:
        if not _assertive_relation(prompt, assessment):
            continue
        window = _exact_window(assessment.item, assessment.span_text)
        if window is None:
            continue
        identity = identity_of(assessment.item).key
        span_id = _span_identity(identity, window)
        authorities.append(
            BooleanEvidenceAuthority(
                evidence_id=identity,
                evidence_ref=span_id,
                span_id=span_id,
                quote=window.text,
                span_start=window.start,
                span_end=window.end,
                canonical_start=window.canonical_start,
                canonical_end=window.canonical_end,
                actor=assessment.proposition.actor,
                section_scope=assessment.proposition.section_scope,
                relation=primary_boolean_relation(prompt),
                object=assessment.proposition.object,
                quantifier=assessment.proposition.quantifier,
                polarity=assessment.proposition.polarity,
                reason=assessment.reason,
            )
        )
    deduplicated = {
        (authority.evidence_id, authority.span_start, authority.span_end): authority
        for authority in authorities
    }
    return tuple(
        sorted(
            deduplicated.values(),
            key=lambda value: (
                -_authority_rank(value),
                value.evidence_id,
                value.span_id,
            ),
        )
    )


def _best_authority(
    values: tuple[BooleanEvidenceAuthority, ...],
) -> BooleanEvidenceAuthority:
    return min(
        values,
        key=lambda value: (-_authority_rank(value), value.evidence_id, value.span_id),
    )


def _authority_rank(value: BooleanEvidenceAuthority) -> int:
    lowered = value.quote.lower()
    qualifiers = (
        "non-significant",
        "non significant",
        "insignificant",
        "small",
        "marginal",
        "only",
        "however",
        "comparing",
    )
    return sum(marker in lowered for marker in qualifiers)


def _exact_window(
    item: dict[str, Any],
    span: str,
) -> PropositionContextWindow | None:
    text = evidence_item_text(item)
    canonical_start = _optional_int(item.get("canonical_start"))
    return exact_proposition_context(
        text,
        span,
        canonical_start=canonical_start,
    )


def _span_identity(identity: str, window: PropositionContextWindow) -> str:
    start = (
        window.canonical_start if window.canonical_start is not None else window.start
    )
    end = window.canonical_end if window.canonical_end is not None else window.end
    return f"{identity}#quote:{start}:{end}"


def _assertive_relation(
    prompt: str,
    assessment: BooleanEvidenceAssessment,
) -> bool:
    span = assessment.span_text.lower()
    relation = primary_boolean_relation(prompt)
    if not relation or relation not in boolean_relation_lemmas(span):
        return False
    if re.search(r"\b(?:discuss|describe|mention)\w*\b", span):
        return False
    return True


def _non_english_result_authority(
    prompt: str,
    evidence_items: list[dict[str, Any]],
) -> tuple[str, BooleanEvidenceAuthority] | None:
    lowered = prompt.lower()
    if not (
        "english" in lowered
        and re.search(r"\b(?:only|exclusively|solely)\b", lowered)
        and re.search(
            r"\b(?:data|dataset|corpus|language|result|experiment)\w*\b", lowered
        )
    ):
        return None
    language = (
        r"(?:non-english|german|french|spanish|chinese|japanese|arabic|multilingual)"
    )
    relation = r"(?:evaluat|experiment|report|result|test|dataset|corpus)\w*"
    candidates: list[BooleanEvidenceAuthority] = []
    for item in evidence_items:
        text = evidence_item_text(item)
        for match in re.finditer(r"[^.!?\n]+(?:[.!?]+|$)", text):
            quote = match.group(0).strip()
            if not (
                re.search(rf"\b{language}\b", quote, flags=re.IGNORECASE)
                and re.search(rf"\b{relation}\b", quote, flags=re.IGNORECASE)
            ):
                continue
            window = _exact_window(item, quote)
            if window is None:
                continue
            identity = identity_of(item).key
            span_id = _span_identity(identity, window)
            candidates.append(
                BooleanEvidenceAuthority(
                    evidence_id=identity,
                    evidence_ref=span_id,
                    span_id=span_id,
                    quote=window.text,
                    span_start=window.start,
                    span_end=window.end,
                    canonical_start=window.canonical_start,
                    canonical_end=window.canonical_end,
                    actor="current_paper",
                    section_scope=str(item.get("section_id") or "document"),
                    relation=primary_boolean_relation(prompt),
                    object="english dataset",
                    quantifier="only",
                    polarity="no",
                    reason="explicit_non_english_counterexample",
                )
            )
    return ("no", _best_authority(tuple(candidates))) if candidates else None


def _required_object_terms(prompt: str) -> set[str]:
    match = re.search(
        r"\b(?:is|are|was|were)\s+(.+?)\s+required\b",
        str(prompt or ""),
        flags=re.IGNORECASE,
    )
    if match is None:
        match = re.search(
            r"\brequire(?:s|d)?\s+(.+?)(?:\?|$)",
            str(prompt or ""),
            flags=re.IGNORECASE,
        )
    return _semantic_terms(match.group(1)) if match is not None else set()


def _semantic_terms(value: str) -> set[str]:
    aliases = {
        "requirements": "requirement",
        "required": "require",
        "requires": "require",
        "requiring": "require",
        "tuning": "tune",
        "embeddings": "embedding",
        "models": "model",
    }
    stop = {
        "are",
        "did",
        "does",
        "existing",
        "fine",
        "into",
        "only",
        "the",
        "these",
        "this",
        "was",
        "were",
    }
    return {
        aliases.get(token, token.rstrip("s") if token.endswith("s") else token)
        for token in re.findall(r"[a-z0-9]+", str(value or "").lower())
        if len(token) > 2 and token not in stop
    }


def _normalized_polarity(value: str) -> str:
    return "yes" if value in {"yes", "true"} else "no"


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
