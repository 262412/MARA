from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .boolean_current_experiment import (
    is_current_experiment_question as _is_current_experiment_question,
)
from .boolean_current_experiment import (
    is_direct_current_empirical_action as _is_direct_current_empirical_action,
)
from .boolean_current_experiment import (
    resolve_current_experiment_question as _resolve_current_experiment_question,
)
from .boolean_evidence_text import (
    _bound_local_context,
    _matching_item,
    _nearest_heading,
    evidence_item_text,
)
from .boolean_ownership_provenance import own_data_provenance_rejection
from .boolean_retrieval_queries import (
    boolean_retrieval_query as _boolean_retrieval_query,
)
from .boolean_scope_quantifiers import (
    _closed_quantifier,
    _english_closed_scope,
    _has_closed_quantifier,
    _language_data_question,
    _non_english_counterexample,
    _quantified_object_scope_complete,
    _scope_excerpt,
)
from .boolean_structured_resolution import structured_boolean_resolutions
from .evidence_identity import identity_of

boolean_retrieval_query = _boolean_retrieval_query


@dataclass(frozen=True)
class BooleanScopeDecision:
    actor: str
    section_role: str
    quantifier: str
    scope_valid: bool
    reason: str

    def as_trace(self) -> dict[str, str]:
        return {
            "boolean_actor": self.actor,
            "boolean_section_role": self.section_role,
            "boolean_quantifier": self.quantifier,
            "boolean_scope_valid": str(self.scope_valid).lower(),
            "boolean_scope_reason": self.reason,
        }


@dataclass(frozen=True)
class ClosedScopeResolution:
    polarity: str
    evidence_quote: str
    decision: BooleanScopeDecision
    evidence_item: dict[str, Any]


def classify_boolean_evidence(
    question: str,
    answer: str,
    item: dict[str, Any],
) -> Any:
    from .boolean_proposition_evidence import classify_boolean_evidence as classify

    return classify(question, answer, item)


def classify_boolean_evidence_set(
    question: str,
    answer: str,
    items: list[dict[str, Any]],
) -> Any:
    from .boolean_proposition_evidence import (
        classify_boolean_evidence_set as classify_set,
    )

    return classify_set(question, answer, items)


def validate_boolean_scope(
    question: str,
    quote: str,
    verdict: str,
    *,
    evidence_items: list[dict[str, Any]] | None = None,
) -> BooleanScopeDecision:
    matching_item = _matching_item(quote, evidence_items or [])
    section_role = _section_role(matching_item, quote)
    context = (
        str(quote or "")
        if _is_current_experiment_question(question)
        else _bound_local_context(matching_item, quote)
    )
    actor = _actor(context, section_role)
    quantifier = _closed_quantifier(question)
    scope_rejection = _scope_rejection(
        question,
        actor=actor,
        section_role=section_role,
        structured_scope_available=bool(matching_item),
        quote=quote,
    )
    if scope_rejection:
        return BooleanScopeDecision(
            actor,
            section_role,
            quantifier,
            False,
            scope_rejection,
        )
    if _is_current_experiment_question(
        question
    ) and not _is_direct_current_empirical_action(quote):
        return BooleanScopeDecision(
            actor,
            section_role,
            quantifier,
            False,
            "current_experiment_action_not_established",
        )
    if quantifier == "none":
        return BooleanScopeDecision(
            actor,
            section_role,
            quantifier,
            True,
            "non_quantified_proposition",
        )
    if not _language_data_question(question):
        return _quantified_scope_decision(
            question,
            quote,
            actor=actor,
            section_role=section_role,
            quantifier=quantifier,
            verdict=verdict,
        )
    return _language_scope_decision(
        actor,
        section_role,
        quantifier,
        quote,
        verdict,
    )


def _quantified_scope_decision(
    question: str,
    quote: str,
    *,
    actor: str,
    section_role: str,
    quantifier: str,
    verdict: str,
) -> BooleanScopeDecision:
    complete = _quantified_object_scope_complete(
        question,
        quote,
        quantifier=quantifier,
        verdict=verdict,
    )
    actor_scope_valid = actor == "current_paper" or (
        actor in {"cited_work", "other_authors"}
        and _prior_work_scope_question(question)
    )
    return BooleanScopeDecision(
        actor,
        section_role,
        quantifier,
        actor_scope_valid and complete,
        (
            "quantified_scope_requires_current_paper_actor"
            if not actor_scope_valid
            else "quantified_object_scope_complete"
            if complete
            else "other_than_alternative_unproven"
            if re.search(r"\bother\s+than\b", question, re.IGNORECASE)
            else "quantified_object_scope_incomplete"
        ),
    )


def _language_scope_decision(
    actor: str,
    section_role: str,
    quantifier: str,
    quote: str,
    verdict: str,
) -> BooleanScopeDecision:
    if actor != "current_paper" or section_role not in {
        "experiments",
        "methods",
        "results",
    }:
        return BooleanScopeDecision(
            actor,
            section_role,
            quantifier,
            False,
            "language_scope_requires_current_experiment_evidence",
        )
    if verdict == "no":
        valid = _non_english_counterexample(quote)
        reason = (
            "current_non_english_counterexample"
            if valid
            else "no_non_english_counterexample"
        )
    elif verdict == "yes":
        valid = _english_closed_scope(quote)
        reason = "current_closed_english_scope" if valid else "english_scope_not_closed"
    else:
        valid = False
        reason = "no_typed_boolean_polarity"
    return BooleanScopeDecision(actor, section_role, quantifier, valid, reason)


def scope_valid_support_items(
    question: str,
    answer: str,
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    classified = classify_boolean_evidence_set(question, answer, items)
    return [assessment.item for assessment in classified.supports]


def resolve_closed_scope_boolean(
    question: str,
    evidence_items: list[dict[str, Any]],
) -> ClosedScopeResolution | None:
    experiment_resolution = _resolve_current_experiment_question(
        question,
        evidence_items,
    )
    if experiment_resolution is not None:
        return experiment_resolution
    structured_resolution = _resolve_structured_boolean(question, evidence_items)
    if structured_resolution is not None:
        return structured_resolution
    if not (_language_data_question(question) and _has_closed_quantifier(question)):
        return None
    supported: dict[str, list[tuple[dict[str, Any], BooleanScopeDecision, str]]] = {
        "yes": [],
        "no": [],
    }
    for item in evidence_items:
        text = evidence_item_text(item)
        if not text:
            continue
        for polarity in supported:
            quote = _scope_excerpt(text, polarity)
            if not quote:
                continue
            decision = validate_boolean_scope(
                question,
                quote,
                polarity,
                evidence_items=[item],
            )
            if decision.scope_valid:
                supported[polarity].append((item, decision, quote))
    polarities = [polarity for polarity, values in supported.items() if values]
    if len(polarities) != 1:
        return None
    polarity = polarities[0]
    item, decision, quote = min(
        supported[polarity],
        key=lambda value: (len(value[2]), value[2]),
    )
    return ClosedScopeResolution(
        polarity=polarity,
        evidence_quote=quote,
        decision=decision,
        evidence_item=item,
    )


def _resolve_structured_boolean(
    question: str,
    evidence_items: list[dict[str, Any]],
) -> ClosedScopeResolution | None:
    candidates: list[tuple[str, dict[str, Any], BooleanScopeDecision, str]] = []
    for item in evidence_items:
        text = evidence_item_text(item)
        for resolution in structured_boolean_resolutions(question, text):
            actor, section_role, rejection = _structured_candidate_scope(
                question,
                item,
                resolution,
            )
            if rejection or actor != "current_paper":
                continue
            decision = BooleanScopeDecision(
                actor=actor,
                section_role=section_role,
                quantifier=resolution.quantifier,
                scope_valid=True,
                reason=resolution.reason,
            )
            candidates.append((resolution.polarity, item, decision, resolution.quote))
    polarities = {value[0] for value in candidates}
    if len(polarities) != 1:
        return None
    polarity = polarities.pop()
    _, item, decision, quote = min(
        candidates,
        key=lambda value: (
            len(value[3]),
            value[3],
            str(identity_of(value[1]).key),
        ),
    )
    return ClosedScopeResolution(
        polarity=polarity,
        evidence_quote=quote,
        decision=decision,
        evidence_item=item,
    )


def _structured_candidate_scope(
    question: str,
    item: dict[str, Any],
    resolution: Any,
) -> tuple[str, str, str]:
    section_role = _section_role(item, resolution.quote)
    actor = _actor(resolution.quote, section_role)
    if (
        actor == "unknown"
        and resolution.reason == "explicit_complete_named_enumeration"
        and re.search(
            r"\b(?:our|we|this|current(?:ly)?)\b",
            resolution.quote,
            flags=re.IGNORECASE,
        )
    ):
        actor = "current_paper"
        if section_role == "unknown":
            section_role = "methods"
    if resolution.reason == "explicit_current_derogatory_label_analysis" and re.search(
        r"\b(?:primary|main)\s+focus\s+of\s+this\s+study\b",
        resolution.quote,
        flags=re.IGNORECASE,
    ):
        actor = "current_paper"
        section_role = "methods"
    rejection = _scope_rejection(
        question,
        actor=actor,
        section_role=section_role,
        structured_scope_available=True,
        quote=resolution.quote,
    )
    if (
        resolution.reason == "explicit_external_collection_provenance"
        and rejection
        in {
            "external_data_source_does_not_establish_own_collection",
            "own_data_provenance_not_established",
        }
    ):
        rejection = ""
    if (
        resolution.reason == "explicit_current_dataset_challenges"
        and actor == "current_paper"
        and section_role == "introduction"
        and rejection == "current_paper_scope_not_established"
    ):
        rejection = ""
    return actor, section_role, rejection


def boolean_proposition_evidence_score(
    question: str,
    item: dict[str, Any],
) -> float:
    from .boolean_proposition_evidence import (
        boolean_proposition_evidence_score as score,
    )

    return score(question, item)


def _actor(quote: str, section_role: str) -> str:
    lowered = str(quote or "").lower()
    explicit_current_actor = bool(
        re.search(
            r"\b(?:i|we|our|current (?:paper|study|work)|"
            r"this (?:paper|article|study|work)|(?:the\s+)?authors?|"
            r"(?:the\s+)?proposed (?:model|method|approach|system))\b",
            lowered,
        )
    )
    if re.search(
        r"\b(?:external|independent|different|outside)\s+"
        r"(?:authors?|researchers?|papers?|stud(?:y|ies)|work)\b",
        lowered,
    ) or re.search(
        r"\bby\s+(?:an?\s+|the\s+)?(?:external|independent|different|outside)\s+"
        r"(?:authors?|researchers?|papers?|stud(?:y|ies)|work)\b",
        lowered,
    ):
        return "other_authors"
    if any(
        marker in lowered
        for marker in (
            "other authors",
            "another paper",
            "another study",
            "other researchers",
            "other paper",
            "other study",
            "other studies",
            "other work",
        )
    ):
        return "other_authors"
    cited_markers = (
        "previous work",
        "prior work",
        "earlier work",
        "related work",
        "recent work",
    )
    if (
        section_role == "related_work"
        or any(marker in lowered for marker in cited_markers)
        or (
            not explicit_current_actor
            and re.search(r"\bbibref\d+\b|\[[0-9, -]+\]", lowered)
        )
        or (
            not explicit_current_actor
            and re.search(
                r"\b(?:prior|previous|earlier|cited)\s+"
                r"(?:model|encoder|system|method|approach|baseline)\b",
                lowered,
            )
        )
        or re.search(
            r"\b(?:prior|previous|earlier|cited|related)\s+"
            r"(?:paper|article|study|research|work)\b",
            lowered,
        )
        or re.search(
            r"\baccording\s+to\s+(?:prior|previous|earlier|cited|related)\s+"
            r"(?:research|work|stud(?:y|ies))\b",
            lowered,
        )
        or re.search(r"\b(?:19|20)\d{2}\s+(?:paper|study|work)\b", lowered)
        or re.search(r"\b[a-z]+(?:\.[a-z]+)+\.\d{4}\b", lowered)
        or re.search(r"\b[a-z][a-z-]+\s+et\s+al\.?\s*(?:19|20)\d{2}\b", lowered)
    ):
        return "cited_work"
    if re.search(r"\b[a-z][a-z-]+\s+et\s+al\.?", lowered):
        return "other_authors"
    if explicit_current_actor:
        return "current_paper"
    if section_role in {"experiments", "methods", "results"}:
        return "current_paper"
    return "unknown"


def _section_role(item: dict[str, Any], quote: str) -> str:
    explicit_values = [
        str(item.get(field) or "")
        for field in ("section_id", "section_title", "section", "heading")
    ]
    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        explicit_values.extend(
            str(metadata.get(field) or "")
            for field in ("section_id", "section_title", "section", "heading")
        )
    explicit_role = _section_role_from_text(" ".join(explicit_values))
    if explicit_role:
        return explicit_role
    heading_role = _section_role_from_text(_nearest_heading(item, quote))
    if heading_role:
        return heading_role
    return _section_role_from_text(str(quote or "")) or "unknown"


def _section_role_from_text(value: str) -> str:
    lowered = re.sub(r"[_-]+", " ", str(value or "").lower())
    if re.search(r"\b(?:related work|background|previous work|prior work)\b", lowered):
        return "related_work"
    if re.search(r"\b(?:future work|limitation)\b", lowered):
        return "future_work"
    if re.search(
        r"\b(?:experiments?|evaluation|evaluate|datasets?|corpora|corpus|"
        r"test(?:ed|ing)?|translated?|translation programs?|for instance|"
        r"unable to construct)\b",
        lowered,
    ):
        return "experiments"
    if re.search(r"\b(?:results?|findings?|performance|scores?)\b", lowered):
        return "results"
    if re.search(
        r"\b(?:method|approach|procedure|annotation|current study|"
        r"we (?:chose|identified|compiled|selected))\b",
        lowered,
    ):
        return "methods"
    if re.search(r"\b(?:introduction|overview|motivation)\b", lowered):
        return "introduction"
    return ""


def _requires_current_paper_scope(question: str) -> bool:
    lowered = str(question or "").lower()
    return bool(
        re.search(
            r"\b(?:the authors?|this (?:paper|article|study|work)|"
            r"current (?:paper|study|work)|they|their)\b",
            lowered,
        )
        or _requires_experiment_scope(question)
    )


def _scope_rejection(
    question: str,
    *,
    actor: str,
    section_role: str,
    structured_scope_available: bool,
    quote: str = "",
) -> str:
    ownership_rejection = own_data_provenance_rejection(question, quote)
    if ownership_rejection:
        return ownership_rejection
    if _prior_work_scope_question(question):
        return ""
    if actor in {"cited_work", "other_authors"} and not _prior_work_scope_question(
        question
    ):
        return "cited_work_does_not_establish_current_paper_claim"
    if not _requires_current_paper_scope(question):
        return ""
    if actor != "current_paper" and (
        structured_scope_available or _requires_experiment_scope(question)
    ):
        return "current_paper_scope_not_established"
    if (
        actor == "current_paper"
        and section_role != "unknown"
        and section_role not in _current_paper_section_roles(question)
    ):
        return "current_paper_scope_not_established"
    return ""


def _prior_work_scope_question(question: str) -> bool:
    return bool(
        re.search(
            r"\b(?:previous|prior|earlier|related)\s+"
            r"(?:work|research|stud(?:y|ies)|papers?)\b",
            str(question or ""),
            flags=re.IGNORECASE,
        )
    )


def _requires_experiment_scope(question: str) -> bool:
    return bool(
        re.search(
            r"\b(?:experiment|evaluate|evaluation|test|task|dataset|"
            r"result|report)\w*\b",
            str(question or "").lower(),
        )
    )


def _current_paper_section_roles(question: str) -> set[str]:
    lowered = str(question or "").lower()
    if _requires_experiment_scope(question):
        return {"experiments", "methods", "results"}
    if re.search(r"\b(?:method|approach|propose|introduce|train|use)\w*\b", lowered):
        return {"introduction", "methods", "results"}
    return {"introduction", "experiments", "methods", "results"}


def _normalized(value: str) -> str:
    return " ".join(str(value or "").lower().split())
