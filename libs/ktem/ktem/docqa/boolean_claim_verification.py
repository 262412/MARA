from __future__ import annotations

import re
from typing import Any

from .boolean_authoritative_conflict import authoritative_conflict_claim
from .boolean_authority_schema import BooleanClaimAuthority, BooleanEvidenceAuthority
from .boolean_evidence_scope import (
    ClosedScopeResolution,
    _actor,
    _scope_rejection,
    _section_role,
    evidence_item_text,
    resolve_closed_scope_boolean,
)
from .boolean_proposition_context import (
    PropositionContextWindow,
    exact_proposition_context,
)
from .boolean_proposition_evidence import (
    BooleanEvidenceAssessment,
    boolean_proposition_object_identity,
    classify_boolean_evidence_set,
    exact_span_asserts_boolean_relation,
    proposition_qualifier,
)
from .boolean_relations import primary_boolean_relation
from .evidence_identity import identity_of
from .evidence_text import extract_final_answer_text
from .query_phrase_extraction import (
    semantic_boolean_proposition_question,
    source_page_locator,
)


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
    *,
    allow_missing_polarity: bool = False,
) -> BooleanClaimAuthority | None:
    input_polarity = canonical_boolean_answer_polarity(answer)
    if not input_polarity and not allow_missing_polarity:
        return None
    probe_polarity = input_polarity or "yes"
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

    classified = classify_boolean_evidence_set(prompt, probe_polarity, evidence_items)
    supporting = _exact_authorities(prompt, classified.supports)
    contradicting = _exact_authorities(prompt, classified.contradicts)
    if supporting and contradicting:
        return authoritative_conflict_claim(
            prompt,
            input_polarity,
            probe_polarity,
            supporting,
            contradicting,
        )
    if supporting:
        return _supported_authority(
            prompt,
            input_polarity,
            probe_polarity,
            supporting,
            reason="exact_boolean_proposition",
        )
    if contradicting:
        canonical_polarity = "no" if probe_polarity == "yes" else "yes"
        return _supported_authority(
            prompt,
            input_polarity,
            canonical_polarity,
            contradicting,
            contradicting=(),
            reason="exact_opposite_boolean_proposition",
        )
    resolved = _negative_requirement_authority(prompt, evidence_items)
    if resolved is not None:
        canonical_polarity, authority = resolved
        return _supported_authority(
            prompt,
            input_polarity,
            canonical_polarity,
            (authority,),
            reason="explicit_requirement_negative_qualifier",
        )
    return BooleanClaimAuthority(
        claim=f"{probe_polarity}: {prompt}",
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
            object=boolean_proposition_object_identity(prompt),
            quantifier=resolution.decision.quantifier,
            polarity=resolution.polarity,
            reason=resolution.decision.reason,
            qualifier=proposition_qualifier(window.text),
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
            polarity = (
                "no"
                if _requirement_negative_clause(quote, question_terms)
                else "yes"
                if asked_object_present
                else "no"
            )
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
                    qualifier=proposition_qualifier(quote),
                )
            )
    polarities = {candidate.polarity for candidate in candidates}
    if len(polarities) != 1 or not candidates:
        return None
    return candidates[0].polarity, _best_authority(tuple(candidates))


def _negative_requirement_authority(
    prompt: str,
    evidence_items: list[dict[str, Any]],
) -> tuple[str, BooleanEvidenceAuthority] | None:
    """Bind explicit negative requirement qualifiers lacking a ``require`` verb."""

    question_terms = _required_object_terms(prompt)
    if not question_terms:
        return None
    candidates: list[BooleanEvidenceAuthority] = []
    for item in evidence_items:
        text = evidence_item_text(item)
        for match in re.finditer(r"[^.!?\n]+(?:[.!?]+|$)", text):
            quote = match.group(0).strip()
            if not _requirement_negative_clause(quote, question_terms):
                continue
            window = _exact_window(item, quote)
            if window is None:
                continue
            section_role = _section_role(item, quote)
            if section_role == "unknown" and re.search(
                r"\bmethods?\b",
                " ".join(
                    str(item.get(field) or "")
                    for field in ("section_id", "section_title", "section", "heading")
                ),
                flags=re.IGNORECASE,
            ):
                section_role = "methods"
            if section_role == "future_work":
                continue
            actor = _actor(quote, section_role)
            if _scope_rejection(
                prompt,
                actor=actor,
                section_role=section_role,
                structured_scope_available=True,
                quote=quote,
            ):
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
                    actor=actor,
                    section_scope=section_role,
                    relation="require",
                    object=" ".join(sorted(question_terms)),
                    quantifier=(
                        "only"
                        if re.search(r"\b(?:only|solely|exclusively)\b", prompt, re.I)
                        else "none"
                    ),
                    polarity="no",
                    reason="explicit_requirement_negative_qualifier",
                    qualifier=proposition_qualifier(quote),
                )
            )
    if not candidates:
        return None
    return "no", _best_authority(tuple(candidates))


def _exact_authorities(
    prompt: str,
    assessments: tuple[BooleanEvidenceAssessment, ...],
) -> tuple[BooleanEvidenceAuthority, ...]:
    authorities: list[BooleanEvidenceAuthority] = []
    for assessment in assessments:
        if not _assertive_relation(prompt, assessment):
            continue
        window = _exact_window(
            assessment.item,
            assessment.span_text,
            question=semantic_boolean_proposition_question(prompt),
        )
        if window is None:
            continue
        identity = identity_of(assessment.item).key
        span_id = _span_identity(identity, window)
        source_id, page_label = source_page_locator(assessment.item)
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
                qualifier=assessment.proposition.qualifier,
                source_id=source_id,
                page_label=page_label,
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
    *,
    question: str = "",
) -> PropositionContextWindow | None:
    text = evidence_item_text(item)
    canonical_start = _optional_int(item.get("canonical_start"))
    return exact_proposition_context(
        text,
        span,
        canonical_start=canonical_start,
        question=question,
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
    semantic_prompt = semantic_boolean_proposition_question(prompt)
    if not exact_span_asserts_boolean_relation(semantic_prompt, span):
        return False
    if assessment.object_score < 1.0 or not assessment.proposition.object:
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
                    qualifier=proposition_qualifier(quote),
                )
            )
    return ("no", _best_authority(tuple(candidates))) if candidates else None


def _required_object_terms(prompt: str) -> set[str]:
    match = re.search(
        r"\b(?:is|are|was|were)\s+(.+?)\s+" r"(?:required|necessary|needed)\b",
        str(prompt or ""),
        flags=re.IGNORECASE,
    )
    if match is None:
        match = re.search(
            r"\brequire(?:s|d)?\s+(.+?)(?:\?|$)",
            str(prompt or ""),
            flags=re.IGNORECASE,
        )
    if match is None:
        match = re.search(
            r"\bmust\s+(.+?)(?:\?|$)",
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


def _requirement_negative_clause(quote: str, question_terms: set[str]) -> bool:
    negative = re.compile(
        r"\b(?:without|unnecessary|optional|not\s+needed|not\s+required|"
        r"does\s+not\s+require|do\s+not\s+require|did\s+not\s+require|"
        r"isn't\s+needed|is\s+not\s+needed)\b",
        flags=re.IGNORECASE,
    )
    for clause in re.split(
        r"(?:[.!?;:]|\bbut\b|\bhowever\b)",
        quote,
        flags=re.IGNORECASE,
    ):
        clause_terms = _semantic_terms(clause)
        if question_terms & clause_terms and negative.search(clause):
            return True
    return False


def _normalized_polarity(value: str) -> str:
    return "yes" if value in {"yes", "true"} else "no"


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
