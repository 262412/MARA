from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .boolean_current_experiment import (
    current_experiment_excerpt as _current_experiment_excerpt,
)
from .boolean_current_experiment import (
    is_current_experiment_question as _is_current_experiment_question,
)
from .boolean_current_experiment import (
    is_direct_current_empirical_action as _is_direct_current_empirical_action,
)
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
) -> BooleanScopeDecision:
    complete = _quantified_object_scope_complete(
        question,
        quote,
        quantifier=quantifier,
    )
    return BooleanScopeDecision(
        actor,
        section_role,
        quantifier,
        actor == "current_paper" and complete,
        (
            "quantified_scope_requires_current_paper_actor"
            if actor != "current_paper"
            else "quantified_object_scope_complete"
            if complete
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


def _resolve_current_experiment_question(
    question: str,
    evidence_items: list[dict[str, Any]],
) -> ClosedScopeResolution | None:
    if not _is_current_experiment_question(question):
        return None
    candidates: list[tuple[dict[str, Any], str, BooleanScopeDecision]] = []
    for item in evidence_items:
        text = evidence_item_text(item)
        if not text:
            continue
        quote = _current_experiment_excerpt(text)
        if not quote:
            continue
        scope_item = {
            **item,
            "text": quote,
            "ocr_text": "",
            "vlm_text": "",
            "caption": "",
        }
        decision = validate_boolean_scope(
            question,
            quote,
            "yes",
            evidence_items=[scope_item],
        )
        if not decision.scope_valid:
            continue
        candidates.append((item, quote, decision))
    if not candidates:
        return None
    item, quote, decision = min(candidates, key=lambda value: len(value[1]))
    return ClosedScopeResolution(
        polarity="yes",
        evidence_quote=quote,
        decision=decision,
        evidence_item=item,
    )


def boolean_proposition_evidence_score(
    question: str,
    item: dict[str, Any],
) -> float:
    from .boolean_proposition_evidence import (
        boolean_proposition_evidence_score as score,
    )

    return score(question, item)


def evidence_item_text(item: dict[str, Any]) -> str:
    return "\n".join(
        str(item.get(field) or "").strip()
        for field in ("text", "ocr_text", "vlm_text", "caption")
        if str(item.get(field) or "").strip()
    )


def _matching_item(
    quote: str,
    items: list[dict[str, Any]],
) -> dict[str, Any]:
    normalized_quote = _normalized(quote)
    for item in items:
        text = _normalized(evidence_item_text(item))
        if normalized_quote and normalized_quote in text:
            return item
    return {}


def _actor(quote: str, section_role: str) -> str:
    lowered = str(quote or "").lower()
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
    )
    if (
        section_role == "related_work"
        or any(marker in lowered for marker in cited_markers)
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
    if re.search(
        r"\b(?:i|we|our|current (?:paper|study|work)|"
        r"(?:this (?:paper|article|study|work))|(?:the\s+)?authors?)\b",
        lowered,
    ):
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


def _bound_local_context(item: dict[str, Any], quote: str) -> str:
    text = evidence_item_text(item)
    normalized_quote = _normalized(quote)
    if not text or not normalized_quote:
        return str(quote or "")
    normalized_text = _normalized(text)
    if normalized_quote not in normalized_text:
        return str(quote or "")
    parts = str(quote or "").strip().split()
    pattern = re.compile(
        r"\s+".join(re.escape(part) for part in parts),
        flags=re.IGNORECASE,
    )
    match = pattern.search(text)
    if match is None:
        return str(quote or "")
    heading = _nearest_heading(item, quote)
    start = max(0, match.start() - 320)
    end = min(len(text), match.end() + 320)
    return "\n".join(part for part in (heading, text[start:end]) if part)


def _nearest_heading(item: dict[str, Any], quote: str) -> str:
    text = evidence_item_text(item)
    if not text:
        return ""
    parts = str(quote or "").strip().split()
    if not parts:
        return ""
    match = re.search(
        r"\s+".join(re.escape(part) for part in parts),
        text,
        flags=re.IGNORECASE,
    )
    prefix = text[: match.start()] if match is not None else text
    headings = re.findall(r"(?m)^\s{0,3}#{1,6}\s+(.+?)\s*$", prefix)
    return headings[-1].strip() if headings else ""


def _section_role_from_text(value: str) -> str:
    lowered = str(value or "").lower()
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
    if re.search(r"\b(?:results?|findings?|performance)\b", lowered):
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
) -> str:
    if actor in {"cited_work", "other_authors"}:
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
