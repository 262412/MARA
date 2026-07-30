from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .boolean_relations import boolean_relations_align, primary_boolean_relation


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


def validate_boolean_scope(
    question: str,
    quote: str,
    verdict: str,
    *,
    evidence_items: list[dict[str, Any]] | None = None,
) -> BooleanScopeDecision:
    matching_item = _matching_item(quote, evidence_items or [])
    section_role = _section_role(matching_item, quote)
    actor = _actor(quote, section_role)
    quantifier = "only" if _has_closed_quantifier(question) else "none"
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
    if quantifier != "only":
        return BooleanScopeDecision(
            actor,
            section_role,
            quantifier,
            True,
            "non_quantified_proposition",
        )
    if not _language_data_question(question):
        return BooleanScopeDecision(
            actor,
            section_role,
            quantifier,
            actor == "current_paper",
            "quantified_scope_requires_current_paper_actor",
        )
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
    return BooleanScopeDecision(
        actor,
        section_role,
        quantifier,
        valid,
        reason,
    )


def scope_valid_support_items(
    question: str,
    answer: str,
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    polarity = _answer_polarity(answer)
    if not polarity:
        return []
    output: list[dict[str, Any]] = []
    for item in items:
        text = evidence_item_text(item)
        if not text:
            continue
        decision = validate_boolean_scope(
            question,
            text,
            polarity,
            evidence_items=[item],
        )
        if decision.scope_valid:
            output.append(item)
    return output


def boolean_retrieval_query(question: str) -> str:
    text = " ".join(str(question or "").split())
    lowered = text.lower()
    if _language_data_question(text) and _has_closed_quantifier(text):
        expansion = (
            "current study experiments results English data "
            "English-speaking countries non-English datasets"
        )
    elif re.search(r"\b(?:experiment|evaluate|test|task)\w*\b", lowered):
        expansion = "current study authors experiments evaluate tested examples results"
    else:
        return text
    return f"{text} {expansion}".strip()


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
    supported: dict[str, list[tuple[dict[str, Any], BooleanScopeDecision]]] = {
        "yes": [],
        "no": [],
    }
    for item in evidence_items:
        text = evidence_item_text(item)
        if not text:
            continue
        for polarity in supported:
            decision = validate_boolean_scope(
                question,
                text,
                polarity,
                evidence_items=[item],
            )
            if decision.scope_valid:
                supported[polarity].append((item, decision))
    polarities = [polarity for polarity, values in supported.items() if values]
    if len(polarities) != 1:
        return None
    polarity = polarities[0]
    item, decision = min(
        supported[polarity],
        key=lambda value: len(evidence_item_text(value[0])),
    )
    return ClosedScopeResolution(
        polarity=polarity,
        evidence_quote=_scope_excerpt(evidence_item_text(item), polarity),
        decision=decision,
    )


def _resolve_current_experiment_question(
    question: str,
    evidence_items: list[dict[str, Any]],
) -> ClosedScopeResolution | None:
    lowered = str(question or "").lower()
    if not (
        re.search(r"\b(?:the authors?|they|this (?:paper|study|work))\b", lowered)
        and re.search(
            r"\b(?:conduct|perform|run|carry out)\w*\s+(?:an?\s+)?experiments?\b",
            lowered,
        )
        and re.search(r"\b(?:tasks?|benchmarks?)\b", lowered)
    ):
        return None
    candidates: list[tuple[str, BooleanScopeDecision]] = []
    for item in evidence_items:
        text = evidence_item_text(item)
        if not text:
            continue
        decision = validate_boolean_scope(
            question,
            text,
            "yes",
            evidence_items=[item],
        )
        if not decision.scope_valid:
            continue
        quote = _current_experiment_excerpt(text)
        if quote:
            candidates.append((quote, decision))
    if not candidates:
        return None
    quote, decision = min(candidates, key=lambda value: len(value[0]))
    return ClosedScopeResolution(
        polarity="yes",
        evidence_quote=quote,
        decision=decision,
    )


def _current_experiment_excerpt(text: str) -> str:
    statements = [
        statement.strip()
        for statement in re.split(r"(?:\r?\n)+|(?<=[.!?])\s+", str(text or ""))
        if statement.strip()
    ]
    current_actor = re.compile(
        r"\b(?:i|we|our|the authors?|this (?:paper|study|work))\b",
        flags=re.IGNORECASE,
    )
    empirical_action = re.compile(
        r"\b(?:experiment|evaluat|test|translat|unable to construct|"
        r"ran|measur|observation|observe)\w*\b",
        flags=re.IGNORECASE,
    )
    return next(
        (
            statement
            for statement in statements
            if current_actor.search(statement) and empirical_action.search(statement)
        ),
        "",
    )


def boolean_proposition_evidence_score(
    question: str,
    item: dict[str, Any],
) -> float:
    text = evidence_item_text(item)
    if not text:
        return 0.0
    section_role = _section_role(item, text)
    actor = _actor(text, section_role)
    if actor == "cited_work":
        return 0.0
    if _language_data_question(question) and _has_closed_quantifier(question):
        valid = any(
            validate_boolean_scope(
                question,
                text,
                verdict,
                evidence_items=[item],
            ).scope_valid
            for verdict in ("yes", "no")
        )
        return 2.0 if valid else 0.0
    if primary_boolean_relation(question) and not boolean_relations_align(
        question,
        text,
    ):
        return 0.0
    if re.search(r"\b(?:experiment|evaluate|test|task)\w*\b", question.lower()):
        if actor == "current_paper" and section_role in {
            "experiments",
            "methods",
            "results",
        }:
            return 2.0
        return 0.0
    question_tokens = _content_tokens(question)
    evidence_tokens = _content_tokens(text)
    if not question_tokens:
        return 0.0
    coverage = len(question_tokens & evidence_tokens) / len(question_tokens)
    if coverage < 0.35:
        return 0.0
    return 1.0 + coverage


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
    cited_markers = (
        "previous work",
        "prior work",
        "earlier work",
        "related work",
        "other studies",
        "other researchers",
    )
    if (
        section_role == "related_work"
        or any(marker in lowered for marker in cited_markers)
        or re.search(r"\b[a-z]+(?:\.[a-z]+)+\.\d{4}\b", lowered)
        or re.search(r"\b[a-z][a-z-]+\s+et\s+al\.?\s*(?:19|20)\d{2}\b", lowered)
    ):
        return "cited_work"
    if re.search(
        r"\b(?:i|we|our|current study|this (?:paper|article|study|work)|"
        r"the authors)\b",
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
    return _section_role_from_text(str(quote or "")) or "unknown"


def _section_role_from_text(value: str) -> str:
    lowered = str(value or "").lower()
    if re.search(r"\b(?:related work|background|previous work|prior work)\b", lowered):
        return "related_work"
    if re.search(
        r"\b(?:experiments?|evaluation|evaluate|datasets?|corpora|corpus|"
        r"test(?:ed|ing)?|translated?|translation programs?|for instance|"
        r"unable to construct)\b",
        lowered,
    ):
        return "experiments"
    if re.search(r"\b(?:result|finding|performance)\b", lowered):
        return "results"
    if re.search(
        r"\b(?:method|approach|procedure|annotation|current study|"
        r"we (?:chose|identified|compiled|selected))\b",
        lowered,
    ):
        return "methods"
    if re.search(r"\b(?:future work|limitation)\b", lowered):
        return "future_work"
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
    if actor == "cited_work":
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


def _has_closed_quantifier(question: str) -> bool:
    return bool(
        re.search(
            r"\b(?:only|exclusively|solely|all)\b",
            str(question or ""),
            flags=re.IGNORECASE,
        )
    )


def _language_data_question(question: str) -> bool:
    lowered = str(question or "").lower()
    return "english" in lowered and bool(
        re.search(r"\b(?:data|dataset|corpus|language|result|experiment)\w*\b", lowered)
    )


def _non_english_counterexample(quote: str) -> bool:
    for statement in re.split(r"(?:\r?\n)+|(?<=[.!?])\s+", str(quote or "")):
        lowered = statement.lower()
        if re.search(
            r"\b(?:non-english|greek|german|french|spanish|chinese|"
            r"japanese|arabic|multilingual)\b",
            lowered,
        ) and re.search(
            r"\b(?:evaluate|evaluated|evaluation|experiment|report|results?|"
            r"test|tested|dataset|corpus)\w*\b",
            lowered,
        ):
            return True
    return False


def _english_closed_scope(quote: str) -> bool:
    lowered = str(quote or "").lower()
    return "english" in lowered and bool(
        re.search(
            r"\b(?:only|exclusively|solely|all (?:the )?(?:data|datasets|corpora)|"
            r"english-speaking countries)\b",
            lowered,
        )
    )


def _answer_polarity(answer: str) -> str:
    normalized = str(answer or "").strip().lower()
    if normalized in {"yes", "true"}:
        return "yes"
    if normalized in {"no", "false"}:
        return "no"
    return ""


def _content_tokens(value: str) -> set[str]:
    stopwords = {
        "are",
        "did",
        "does",
        "only",
        "the",
        "they",
        "was",
        "were",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(value or "").lower())
        if len(token) > 2 and token not in stopwords
    }


def _scope_excerpt(text: str, polarity: str) -> str:
    lowered = text.lower()
    markers = (
        ("non-english", "greek", "german", "french", "multilingual")
        if polarity == "no"
        else ("english-speaking countries", "english datasets", "english data")
    )
    position = next(
        (lowered.find(marker) for marker in markers if marker in lowered),
        0,
    )
    start = max(0, position - 360)
    end = min(len(text), position + 280)
    return text[start:end].strip()


def _normalized(value: str) -> str:
    return " ".join(str(value or "").lower().split())
