from __future__ import annotations

import ast
import re
from collections.abc import Mapping
from typing import Any

_WORD_RE = re.compile(r"[A-Za-z0-9]+")
_RATING_RE = re.compile(
    r"\b(?:average\s+)?rating(?:\s+of)?\s+(\d+(?:\.\d+)?)\s+stars?\b",
    re.IGNORECASE,
)
_PROPERTY_RE = re.compile(r"\b(?:rich|high|low)\s+in\s+([^.,;:-]+)", re.IGNORECASE)
_REVIEW_COUNT_RE = re.compile(
    r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)"
    r"\s+(?:customer\s+)?reviews?\b",
    re.IGNORECASE,
)
_RELATION_CHANGE_PAIRS = (
    (
        re.compile(r"(?<!\w)offer(?:s|ed|ing)?\b", re.IGNORECASE),
        re.compile(r"\baccept(?:s|ed|ing)?\b", re.IGNORECASE),
    ),
)
_QUALIFIER_WORDS = {
    "all",
    "always",
    "best",
    "every",
    "first",
    "highest",
    "largest",
    "least",
    "longest",
    "lowest",
    "most",
    "never",
    "only",
    "shortest",
    "smallest",
    "worst",
}
_NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}
_STRUCTURED_WRAPPER_WORDS = {
    "a",
    "adding",
    "and",
    "another",
    "appeal",
    "are",
    "as",
    "at",
    "by",
    "customer",
    "customers",
    "described",
    "describes",
    "disappointment",
    "encouraged",
    "expresses",
    "for",
    "has",
    "her",
    "him",
    "his",
    "in",
    "is",
    "it",
    "its",
    "however",
    "local",
    "location",
    "mentioned",
    "near",
    "of",
    "on",
    "one",
    "restaurant",
    "business",
    "review",
    "reviews",
    "sadness",
    "seems",
    "that",
    "the",
    "their",
    "them",
    "this",
    "to",
    "unfortunately",
    "was",
    "where",
    "which",
    "with",
}
_INTRO_WRAPPER_WORDS = {
    "based",
    "can",
    "follow",
    "given",
    "here",
    "how",
    "make",
    "outlined",
    "provided",
    "passage",
    "passages",
    "some",
    "steps",
    "these",
    "you",
}
_NONFACTUAL_PREFIXES = (
    "additionally there may be local regulations",
    "based on the provided passages",
    "here s my answer based on the provided passages",
    "here is a summary",
    "here s a summary",
    "if such information is required",
    "if the passages did not contain",
    "if you are unsure",
    "it is important to note",
    "it is always best to consult",
    "it s important to note",
    "however the passages do not directly mention",
    "note that the passage does not provide",
    "note that the passages do not provide",
    "please note that the passage does not mention",
    "please note that the passages do not mention",
    "therefore the answer to the question",
    "therefore i cannot answer",
    "the passages do not provide detailed instructions",
    "the passages do not provide specific information",
    "unable to answer based on given passages",
)


def structured_claim_supported(source: str, claim: str) -> bool:
    payload = _mapping_payload(source)
    if payload is None:
        return False
    field_comparison = _structured_field_comparison(payload, claim)
    if field_comparison is not None:
        return field_comparison
    return (
        _rating_supported(payload, claim)
        or _ambience_supported(payload, claim)
        or _intro_supported(source, claim)
        or _nonfactual_response_claim(claim)
        or (not _is_passage_qa(payload) and _structured_text_supported(source, claim))
    )


def lexical_claim_supported(source: str, claim: str) -> bool:
    if claim_support_conflict(source, claim):
        return False
    if _passage_advice_supported(source, claim):
        return True
    source_tokens = set(_tokens(" ".join(source_support_units(source))))
    claim_tokens = {
        token
        for token in _tokens(claim)
        if token not in _STRUCTURED_WRAPPER_WORDS and token not in _INTRO_WRAPPER_WORDS
    }
    if len(claim_tokens) < 2:
        return False
    claim_numbers = {token for token in claim_tokens if token.isdigit()}
    if not claim_numbers <= source_tokens:
        return False
    overlap = len(claim_tokens & source_tokens) / len(claim_tokens)
    return overlap >= 0.70


def source_support_units(source: str) -> list[str]:
    payload = _mapping_payload(source)
    if payload is None:
        return [str(source or "")]
    output: list[str] = []
    _append_text_values(payload, output)
    return output or [str(source or "")]


def passage_novelty_indices(source: str, claims: list[str]) -> set[int]:
    payload = _mapping_payload(source)
    is_passage_qa = payload is not None and _is_passage_qa(payload)
    source_tokens = set(_tokens(source))
    selected: set[int] = set()
    for index, claim in enumerate(claims):
        if _intro_supported(source, claim) or _nonfactual_response_claim(claim):
            continue
        if lexical_claim_supported(source, claim) or structured_claim_supported(
            source, claim
        ):
            continue
        if _directional_relation_change(source, claim):
            selected.add(index)
            continue
        if not is_passage_qa:
            continue
        claim_tokens = {
            token
            for token in _tokens(claim)
            if token not in _STRUCTURED_WRAPPER_WORDS
            and token not in _INTRO_WRAPPER_WORDS
        }
        novel = claim_tokens - source_tokens
        if _novel_property_claim(claim, source_tokens) or (
            len(novel) >= 2 and len(novel) / max(len(claim_tokens), 1) >= 0.55
        ):
            selected.add(index)
    return selected


def structured_mismatch_indices(source: str, claims: list[str]) -> set[int]:
    payload = _mapping_payload(source)
    if payload is None or _is_passage_qa(payload):
        return set()
    return {
        index
        for index, claim in enumerate(claims)
        if _structured_field_comparison(payload, claim) is False
    }


def claim_support_conflict(source: str, claim: str) -> bool:
    if _nonfactual_response_claim(claim) or _intro_supported(source, claim):
        return False
    if _directional_relation_change(source, claim):
        return True
    source_tokens = set(_tokens(source))
    claim_tokens = set(_tokens(claim))
    unsupported_qualifiers = (claim_tokens & _QUALIFIER_WORDS) - source_tokens
    if "every" in unsupported_qualifiers and "each" in source_tokens:
        unsupported_qualifiers.remove("every")
    if unsupported_qualifiers:
        return True
    payload = _mapping_payload(source)
    return payload is not None and _structured_field_comparison(payload, claim) is False


def _mapping_payload(source: str) -> Mapping[str, Any] | None:
    try:
        payload = ast.literal_eval(str(source or "").strip())
    except (SyntaxError, ValueError):
        return None
    return payload if isinstance(payload, Mapping) else None


def _append_text_values(value: Any, output: list[str]) -> None:
    if isinstance(value, Mapping):
        for nested in value.values():
            _append_text_values(nested, output)
        return
    if isinstance(value, (list, tuple, set)):
        for nested in value:
            _append_text_values(nested, output)
        return
    if isinstance(value, str):
        text = value.strip()
        if text:
            output.append(text)


def _rating_supported(payload: Mapping[str, Any], claim: str) -> bool:
    match = _RATING_RE.search(claim)
    if match is None:
        return False
    source_rating = payload.get("business_stars")
    try:
        return float(str(source_rating)) == float(match.group(1))
    except (TypeError, ValueError):
        return False


def _structured_field_comparison(
    payload: Mapping[str, Any],
    claim: str,
) -> bool | None:
    normalized = " ".join(_tokens(claim))
    attributes = payload.get("attributes")
    attributes = attributes if isinstance(attributes, Mapping) else {}
    comparisons = _attribute_comparisons(attributes, normalized)

    has_hours, hours_comparison = _hours_comparison(payload.get("hours"), normalized)
    if has_hours:
        comparisons.append(hours_comparison)

    has_review_count, review_comparison = _review_count_comparison(
        payload.get("review_info"),
        normalized,
    )
    if has_review_count:
        comparisons.append(review_comparison)

    if not comparisons:
        return None
    if any(comparison is False for comparison in comparisons):
        return False
    if any(comparison is None for comparison in comparisons):
        return None
    return True


def _attribute_comparisons(
    attributes: Mapping[str, Any],
    claim: str,
) -> list[bool | None]:
    comparisons: list[bool | None] = []
    if re.search(r"\b(?:wi fi|wifi|wireless internet)\b", claim):
        comparisons.append(_wifi_matches(_mapping_value(attributes, "WiFi"), claim))

    boolean_fields = (
        ("outdoor seating", "OutdoorSeating", "outdoor seating"),
        ("reservation", "RestaurantsReservations", "reservation"),
        ("good for group", "RestaurantsGoodForGroups", "groups"),
    )
    for marker, field, negative_term in boolean_fields:
        if marker not in claim:
            continue
        comparisons.append(
            _boolean_attribute_matches(
                _mapping_value(attributes, field),
                expected=not _claim_is_negative(claim, negative_term),
            )
        )
    return comparisons


def _wifi_matches(actual: Any, claim: str) -> bool | None:
    expected = _wifi_claim_value(claim)
    if actual is _MISSING or actual is None or expected is None:
        return None
    actual_value = str(actual).strip().lower()
    if expected == "present":
        return actual_value not in {"", "false", "no", "none"}
    return actual_value == expected


def _hours_comparison(hours: Any, claim: str) -> tuple[bool, bool | None]:
    if not re.search(r"\b(?:open|closed|operates?|hours?)\b", claim):
        return False, None
    day = next(
        (
            name
            for name in (
                "Monday",
                "Tuesday",
                "Wednesday",
                "Thursday",
                "Friday",
                "Saturday",
                "Sunday",
            )
            if name.lower() in claim
        ),
        "",
    )
    if not day:
        return False, None
    actual = _mapping_value(hours, day) if isinstance(hours, Mapping) else _MISSING
    if actual is _MISSING or actual is None:
        return True, None
    actual_closed = _hours_are_closed(str(actual))
    expected_open = not _claim_is_negative(claim, day.lower()) and "closed" not in claim
    return True, expected_open is not actual_closed


def _review_count_comparison(reviews: Any, claim: str) -> tuple[bool, bool | None]:
    match = _REVIEW_COUNT_RE.search(claim)
    if match is None:
        return False, None
    if not isinstance(reviews, (list, tuple)):
        return True, None
    raw_count = match.group(1).lower()
    expected_count = int(raw_count) if raw_count.isdigit() else _NUMBER_WORDS[raw_count]
    return True, len(reviews) == expected_count


_MISSING = object()


def _mapping_value(mapping: Mapping[str, Any], key: str) -> Any:
    normalized_key = re.sub(r"[^a-z0-9]", "", key.lower())
    for candidate, value in mapping.items():
        if re.sub(r"[^a-z0-9]", "", str(candidate).lower()) == normalized_key:
            return value
    return _MISSING


def _wifi_claim_value(claim: str) -> str | None:
    if _claim_is_negative(claim, "wi fi") or _claim_is_negative(claim, "wifi"):
        return "no"
    if "free" in claim:
        return "free"
    if "paid" in claim:
        return "paid"
    if re.search(r"\b(?:has|have|offers?|provides?|available)\b", claim):
        return "present"
    return None


def _boolean_attribute_matches(actual: Any, *, expected: bool) -> bool | None:
    if actual is _MISSING or actual is None:
        return None
    if isinstance(actual, bool):
        return actual is expected
    normalized = str(actual).strip().lower()
    if normalized in {"true", "yes"}:
        return expected
    if normalized in {"false", "no"}:
        return not expected
    return None


def _claim_is_negative(claim: str, term: str) -> bool:
    position = claim.find(term)
    if position < 0:
        return False
    prefix = claim[max(0, position - 28) : position]
    return bool(
        re.search(
            r"\b(?:does not|do not|not|no|without|lacks?|doesn t|don t)\b",
            prefix,
        )
    )


def _hours_are_closed(value: str) -> bool:
    normalized = re.sub(r"\s+", "", value.lower())
    return normalized in {"0:0-0:0", "00:00-00:00", "closed", "none", ""}


def _passage_advice_supported(source: str, claim: str) -> bool:
    payload = _mapping_payload(source)
    if payload is None or not _is_passage_qa(payload):
        return False
    source_text = " ".join(source_support_units(source)).lower()
    claim_text = str(claim or "").lower()
    source_avoids_phone = bool(
        re.search(
            r"\b(?:avoid|do not use|don['’]?t use|stay off)\b[^.]{0,32}"
            r"\b(?:landline\s+)?phones?\b",
            source_text,
        )
    )
    claim_avoids_phone = bool(
        re.search(
            r"\b(?:avoid|do not use|don['’]?t use|stay off)\b[^.]{0,32}"
            r"\b(?:using\s+)?(?:landline\s+)?phones?\b",
            claim_text,
        )
    )
    if not source_avoids_phone or not claim_avoids_phone:
        return False
    if "lightning" in claim_text and "lightning" not in source_text:
        return False
    alternatives = ("cordless", "cell phone")
    return all(term not in claim_text or term in source_text for term in alternatives)


def _ambience_supported(payload: Mapping[str, Any], claim: str) -> bool:
    attributes = payload.get("attributes")
    if not isinstance(attributes, Mapping):
        return False
    ambience = attributes.get("Ambience")
    if not isinstance(ambience, Mapping):
        return False
    normalized_claim = " ".join(_WORD_RE.findall(claim.lower()))
    mentioned = [
        str(name).lower()
        for name in ambience
        if re.search(rf"\b{re.escape(str(name).lower())}\b", normalized_claim)
    ]
    if not mentioned:
        return False
    for name in mentioned:
        expected = _claim_attribute_value(normalized_claim, name)
        if bool(ambience.get(name)) is not expected:
            return False
    return True


def _claim_attribute_value(claim: str, name: str) -> bool:
    position = claim.find(name)
    clause_start = max(claim.rfind("but", 0, position), claim.rfind(",", 0, position))
    clause = claim[clause_start + 1 : position]
    return not bool(re.search(r"\b(?:no|not|without)\b", clause))


def _structured_text_supported(source: str, claim: str) -> bool:
    source_tokens = set(_tokens(source))
    claim_tokens = [
        token for token in _tokens(claim) if token not in _STRUCTURED_WRAPPER_WORDS
    ]
    if len(set(claim_tokens)) < 2:
        return False
    return all(
        token in source_tokens or (token.endswith("s") and token[:-1] in source_tokens)
        for token in claim_tokens
    )


def _intro_supported(source: str, claim: str) -> bool:
    normalized = str(claim or "").strip().lower()
    if _question_restatement_intro(source, normalized):
        return True
    if not normalized.endswith(":"):
        return False
    source_tokens = set(_tokens(source))
    claim_tokens = {
        token
        for token in _tokens(claim)
        if token not in _STRUCTURED_WRAPPER_WORDS and token not in _INTRO_WRAPPER_WORDS
    }
    return len(claim_tokens) >= 2 and claim_tokens <= source_tokens


def _question_restatement_intro(source: str, claim: str) -> bool:
    if not claim.startswith("to ") or "strateg" not in claim:
        return False
    payload = _mapping_payload(source)
    if payload is None or not _is_passage_qa(payload):
        return False
    question_tokens = {
        token
        for token in _tokens(str(payload.get("question") or ""))
        if token not in {"do", "how", "i"}
    }
    claim_tokens = set(_tokens(claim))
    return len(question_tokens) >= 3 and question_tokens <= claim_tokens


def _nonfactual_response_claim(claim: str) -> bool:
    if str(claim or "").strip().endswith("?"):
        return True
    normalized = " ".join(_tokens(claim))
    return any(normalized.startswith(prefix) for prefix in _NONFACTUAL_PREFIXES)


def _is_passage_qa(payload: Mapping[str, Any]) -> bool:
    return "question" in payload and "passages" in payload


def _novel_property_claim(claim: str, source_tokens: set[str]) -> bool:
    for match in _PROPERTY_RE.finditer(claim):
        property_tokens = {
            token
            for token in _tokens(match.group(1))
            if token not in _STRUCTURED_WRAPPER_WORDS
        }
        if property_tokens - source_tokens:
            return True
    return False


def _directional_relation_change(source: str, claim: str) -> bool:
    source_tokens = set(_tokens(source))
    claim_tokens = set(_tokens(claim))
    shared_context = (
        (source_tokens & claim_tokens)
        - _STRUCTURED_WRAPPER_WORDS
        - _INTRO_WRAPPER_WORDS
    )
    if len(shared_context) < 2:
        return False
    return any(
        source_relation.search(source)
        and not claim_relation.search(source)
        and claim_relation.search(claim)
        for source_relation, claim_relation in _RELATION_CHANGE_PAIRS
    )


def _tokens(value: str) -> list[str]:
    normalized = re.sub(r"n['’]t\b", " not", str(value or "").lower())
    return _WORD_RE.findall(normalized)
