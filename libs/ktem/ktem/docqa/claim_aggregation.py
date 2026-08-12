from __future__ import annotations

import re
from typing import Any

from .claim_clauses import split_claim_text
from .claim_filtering import clean_answer_text

CLAIM_AGGREGATION_CONTRACT = "claim_aggregation.v1"
CLAIM_KEY_CONTRACT = "typed_claim_key.v1"

_INLINE_CITATION_RE = re.compile(r"\[\s*\d+(?:\s*[,\]]\s*\d+)*\s*\]")
_SOURCE_CITATION_RE = re.compile(r"\b[^\s#]+#(?:page:[^\s,;]+|source)\b")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?!\[\s*\d)|\n+")
_TOKEN_RE = re.compile(r"[a-z0-9%$€£¥]+", re.IGNORECASE)
_NUMBER_RE = re.compile(r"(?<!\w)[+-]?(?:\d[\d,]*)(?:\.\d+)?%?")
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_UNIT_RE = re.compile(
    r"\b(?:percent|percentage|million|billion|thousand|usd|eur|gbp|ratio)\b|[%$€£¥]",
    re.IGNORECASE,
)
_SYNONYMS = {
    "amounted": "amount",
    "increased": "increase",
    "increases": "increase",
    "rose": "increase",
    "rise": "increase",
    "higher": "increase",
    "grew": "increase",
    "growth": "increase",
    "reported": "report",
    "decreased": "decrease",
    "declined": "decrease",
    "decline": "decrease",
    "fell": "decrease",
    "lower": "decrease",
}
_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "by",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "the",
    "to",
    "was",
    "were",
}
_RELATIONS = {
    "account": "account_for",
    "amount": "equal",
    "comprise": "account_for",
    "decrease": "decrease",
    "equal": "equal",
    "exceed": "exceed",
    "include": "include",
    "increase": "increase",
    "outperform": "outperform",
    "report": "equal",
    "represent": "account_for",
    "total": "equal",
}
_SCOPE_TOKENS = {
    "companywide": "consolidated",
    "consolidated": "consolidated",
    "fiscal": "",
    "group": "",
    "global": "global",
    "worldwide": "global",
}


def aggregate_answer_claims(answer: str) -> tuple[str, dict[str, Any]]:
    text = str(answer or "").strip()
    trace: dict[str, Any] = {
        "contract_id": CLAIM_AGGREGATION_CONTRACT,
        "input_claim_count": 0,
        "output_claim_count": 0,
        "duplicate_claim_count": 0,
        "conflict_count": 0,
        "citation_union_count": 0,
        "claim_key_contract": CLAIM_KEY_CONTRACT,
        "bypassed": False,
    }
    if not text or _structured_output(text):
        trace["bypassed"] = True
        return text, trace

    claims = [_claim_record(chunk) for chunk in _claim_chunks(text)]
    claims = [claim for claim in claims if claim["text"]]
    trace["input_claim_count"] = len(claims)
    selected: list[dict[str, Any]] = []
    for claim in claims:
        duplicate = next(
            (existing for existing in selected if _same_fact(existing, claim)),
            None,
        )
        if duplicate is not None:
            before = len(duplicate["citations"])
            duplicate["citations"] = _unique(
                duplicate["citations"] + claim["citations"]
            )
            trace["duplicate_claim_count"] += 1
            trace["citation_union_count"] += max(
                0, len(duplicate["citations"]) - before
            )
            continue
        trace["conflict_count"] += sum(
            _claims_conflict(existing, claim) for existing in selected
        )
        selected.append(claim)

    trace["output_claim_count"] = len(selected)
    return "\n".join(_render_claim(claim) for claim in selected), trace


def _claim_chunks(answer: str) -> list[str]:
    cleaned = clean_answer_text(answer)
    return [
        clause
        for chunk in _SENTENCE_SPLIT_RE.split(cleaned)
        for clause in split_claim_text(chunk)
        if clause
    ]


def _claim_record(chunk: str) -> dict[str, Any]:
    citations = _unique(
        _INLINE_CITATION_RE.findall(chunk) + _SOURCE_CITATION_RE.findall(chunk)
    )
    text = _INLINE_CITATION_RE.sub(" ", chunk)
    text = _SOURCE_CITATION_RE.sub(" ", text)
    text = re.sub(r"^\s*(?:[-*]|\d+[.)])\s+", "", text)
    text = " ".join(text.split()).strip()
    tokens = _canonical_tokens(text)
    claim_key = _typed_claim_key(tokens, text)
    return {
        "text": text,
        "citations": citations,
        "tokens": tokens,
        "numbers": _normalized_matches(_NUMBER_RE, text),
        "years": _normalized_matches(_YEAR_RE, text),
        "units": _normalized_matches(_UNIT_RE, text),
        "polarity": _polarity(tokens),
        "claim_key": claim_key,
    }


def _same_fact(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if _fact_fields_conflict(left, right):
        return False
    left_key = left["claim_key"]
    right_key = right["claim_key"]
    if not left_key["subject"] or not right_key["subject"]:
        return False
    return all(
        left_key[field] == right_key[field]
        for field in ("subject", "relation", "value", "unit", "time", "polarity")
    ) and (
        left_key["scope"] == right_key["scope"]
        or not left_key["scope"]
        or not right_key["scope"]
    )


def _claims_conflict(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if not _fact_fields_conflict(left, right):
        return False
    left_subject = _subject_tokens(left)
    right_subject = _subject_tokens(right)
    if not left_subject or not right_subject:
        return False
    return (
        len(left_subject & right_subject) / min(len(left_subject), len(right_subject))
        >= 0.5
    )


def _fact_fields_conflict(left: dict[str, Any], right: dict[str, Any]) -> bool:
    for field in ("numbers", "years", "units"):
        left_values = set(left[field])
        right_values = set(right[field])
        if left_values and right_values and left_values != right_values:
            return True
    return bool(
        left["polarity"] and right["polarity"] and left["polarity"] != right["polarity"]
    )


def _subject_tokens(claim: dict[str, Any]) -> set[str]:
    return set(claim["claim_key"]["subject"])


def _typed_claim_key(tokens: list[str], text: str) -> dict[str, tuple[str, ...] | str]:
    relation_index, relation = _relation(tokens)
    subject_source = tokens[:relation_index] if relation_index is not None else tokens
    years = set(_normalized_matches(_YEAR_RE, text))
    values = tuple(
        value for value in _normalized_matches(_NUMBER_RE, text) if value not in years
    )
    units = tuple(_normalized_matches(_UNIT_RE, text))
    scope = tuple(
        dict.fromkeys(
            normalized
            for token in tokens
            if token in _SCOPE_TOKENS and (normalized := _SCOPE_TOKENS[token])
        )
    )
    subject = tuple(
        token
        for token in subject_source
        if token not in years
        and token not in values
        and token not in units
        and token not in _SCOPE_TOKENS
        and token not in _RELATIONS
    )
    relation_token = tokens[relation_index] if relation_index is not None else ""
    if relation == "equal" and (relation_token == "report" or not subject):
        metric_subject = _reported_metric_subject(
            tokens,
            relation_index,
            years=years,
            values=set(values),
            units=set(units),
        )
        if metric_subject:
            subject = metric_subject
    return {
        "subject": subject,
        "relation": relation,
        "value": values,
        "unit": units,
        "time": tuple(sorted(years)),
        "scope": scope,
        "polarity": _polarity(tokens),
    }


def _reported_metric_subject(
    tokens: list[str],
    relation_index: int | None,
    *,
    years: set[str],
    values: set[str],
    units: set[str],
) -> tuple[str, ...]:
    if relation_index is None:
        return ()
    candidates = [
        token
        for token in tokens[relation_index + 1 :]
        if token not in years
        and token not in values
        and token not in units
        and token not in _STOPWORDS
        and token not in _RELATIONS
        and token not in {"company", "group"}
    ]
    return tuple(candidates[-1:])


def _relation(tokens: list[str]) -> tuple[int | None, str]:
    for index, token in enumerate(tokens):
        if token in _RELATIONS:
            return index, _RELATIONS[token]
    return None, ""


def _canonical_tokens(text: str) -> list[str]:
    output = []
    for token in _TOKEN_RE.findall(text.lower()):
        token = _SYNONYMS.get(token, token)
        if token not in _STOPWORDS:
            output.append(token)
    return output


def _normalized_matches(pattern: re.Pattern[str], text: str) -> list[str]:
    return sorted(
        {
            str(value).lower().replace(",", "")
            for value in pattern.findall(text)
            if str(value).strip()
        }
    )


def _polarity(tokens: list[str]) -> str:
    if "increase" in tokens:
        return "positive"
    if "decrease" in tokens:
        return "negative"
    return ""


def _render_claim(claim: dict[str, Any]) -> str:
    citation_text = "".join(
        citation if citation.startswith("[") else f" {citation}"
        for citation in claim["citations"]
    )
    if citation_text.startswith("["):
        citation_text = f" {citation_text}"
    text = str(claim["text"] or "").strip()
    trailing = ""
    while text and text[-1] in ".!?":
        trailing = text[-1] + trailing
        text = text[:-1].rstrip()
    return f"{text}{citation_text}{trailing}".strip()


def _structured_output(text: str) -> bool:
    stripped = text.strip()
    if stripped.startswith(("{", "[")):
        return True
    if "$$" in stripped or "\\[" in stripped or "\\(" in stripped:
        return True
    return any(
        line.strip().startswith("|") and line.strip().endswith("|")
        for line in stripped.splitlines()
    )


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
