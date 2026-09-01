from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from typing import Any, Mapping, Sequence

from .boolean_proposition_polarity import evidence_polarity
from .question_proposition import TypedConclusion

POLARITY_CONTRADICTION_CHECK_CONTRACT = "polarity_contradiction_check.v1"


@dataclass(frozen=True, slots=True)
class PolarityContradictionCheck:
    """Model-independent polarity check over the exact selected quotes."""

    conclusion_id: str
    status: str
    observed_polarities: tuple[str, ...]
    quote_digests: tuple[str, ...]
    method: str = "deterministic_exact_quote_polarity"
    independent_from_models: bool = True
    contract_id: str = POLARITY_CONTRADICTION_CHECK_CONTRACT

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["observed_polarities"] = list(self.observed_polarities)
        payload["quote_digests"] = list(self.quote_digests)
        return payload


def polarity_contradiction_check(
    conclusion: TypedConclusion,
    premises: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    quotes = [str(premise.get("quote") or "") for premise in premises]
    observed = tuple(
        _observed_polarity(conclusion, quote) or "unknown" for quote in quotes
    )
    opposite = "no" if conclusion.polarity == "yes" else "yes"
    if opposite in observed:
        status = "contradiction_detected"
    elif conclusion.polarity in observed:
        status = "aligned"
    else:
        status = "no_explicit_contradiction"
    return PolarityContradictionCheck(
        conclusion_id=conclusion.conclusion_id,
        status=status,
        observed_polarities=observed,
        quote_digests=tuple(_text_digest(quote) for quote in quotes),
    ).as_dict()


def polarity_contradiction_check_validation_reason(
    value: Any,
    conclusion: TypedConclusion,
    premises: Sequence[Mapping[str, Any]],
) -> str:
    expected = polarity_contradiction_check(conclusion, premises)
    if not isinstance(value, Mapping) or dict(value) != expected:
        return "polarity_contradiction_check_binding_invalid"
    if value.get("status") == "contradiction_detected":
        return "polarity_contradiction_detected"
    return ""


def _observed_polarity(conclusion: TypedConclusion, quote: str) -> str:
    relation_negative = _typed_relation_negative(conclusion.predicate, quote)
    if relation_negative is not None:
        return "yes" if relation_negative == conclusion.negated else "no"
    observed = evidence_polarity(
        conclusion.surface,
        quote,
        desired_polarity=conclusion.polarity,
    )
    if observed:
        return observed
    return ""


def _typed_relation_negative(predicate: str, quote: str) -> bool | None:
    patterns = {
        "add": r"\badd(?:s|ed|ing)?\b",
        "annotate": r"\bannotat(?:e|es|ed|ing)\b",
        "associate": r"\bassociat(?:e|es|ed|ing)\b",
        "be_collection_of": r"\bcollection\s+of\b",
        "be_subject_to": r"\bsubject(?:ed)?\s+to\b",
        "cause": r"\b(?:caus(?:e|es|ed|ing)|result(?:s|ed|ing)?\s+in)\b",
        "collect": r"\bcollect(?:s|ed|ing)?\b",
        "focus_on": r"\bfocus(?:es|ed|ing)?\s+on\b",
        "have": r"\b(?:have|has|had)\b",
        "help": r"\bhelp(?:s|ed|ing)?\b",
        "inspect": r"\binspect(?:s|ed|ing)?\b",
    }
    pattern = patterns.get(predicate)
    if pattern is None:
        return None
    matches = list(re.finditer(pattern, quote, flags=re.IGNORECASE))
    if len(matches) != 1:
        return None
    start = matches[0].start()
    left = quote[max(0, start - 48) : start]
    return bool(
        re.search(
            r"\b(?:do|does|did|is|are|was|were|has|have|had|can|could|will|"
            r"would)?\s*(?:not|never)\b[^.!?]*$|\bno\b[^.!?]*$",
            left,
            flags=re.IGNORECASE,
        )
    )


def _text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
