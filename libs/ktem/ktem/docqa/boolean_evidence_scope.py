from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


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
    if actor == "cited_work":
        return BooleanScopeDecision(
            actor,
            section_role,
            quantifier,
            False,
            "cited_work_does_not_establish_current_paper_claim",
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
    return "unknown"


def _section_role(item: dict[str, Any], quote: str) -> str:
    values = [
        str(item.get(field) or "")
        for field in ("section_id", "section_title", "section", "heading")
    ]
    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        values.extend(
            str(metadata.get(field) or "")
            for field in ("section_id", "section_title", "section", "heading")
        )
    lowered = " ".join([*values, str(quote or "")]).lower()
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
    return "unknown"


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
