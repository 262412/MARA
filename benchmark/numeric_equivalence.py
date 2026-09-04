from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal

NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")
PERCENT_RE = re.compile(r"%|\bpercent(?:age)?\b", flags=re.IGNORECASE)
APPROXIMATION_RE = re.compile(
    r"[~≈]|\b(?:about|approx(?:imately)?|roughly)\b",
    flags=re.IGNORECASE,
)


def numeric_tolerance_score(
    prediction: str,
    gold_answers: list[str],
    tolerance: float = 0.001,
) -> float:
    predicted = _extract_number(prediction)
    if predicted is None or not gold_answers:
        return 0.0
    for answer in gold_answers:
        gold = _extract_number(answer)
        if gold is None:
            continue
        allowed_delta = abs(gold) * tolerance
        if abs(predicted - gold) <= allowed_delta:
            return 1.0
        if _explicit_approximate_percentage_match(
            prediction,
            predicted,
            answer,
            gold,
        ):
            return 1.0
    return 0.0


def _extract_number(text: str) -> float | None:
    match = _selected_number_match(text)
    if match is None:
        return None
    return float(match.group(0).replace(",", ""))


def _selected_number_match(text: str) -> re.Match[str] | None:
    value = str(text or "")
    matches = list(NUMBER_RE.finditer(value))
    if not matches:
        return None
    return next(
        (match for match in matches if not _looks_like_year(value, match)),
        matches[0],
    )


def _looks_like_year(text: str, match: re.Match[str]) -> bool:
    raw = match.group(0)
    if "." in raw or re.search(r"\d,\d{3}", raw):
        return False
    try:
        number = int(raw.rstrip(","))
    except ValueError:
        return False
    if not 1900 <= number <= 2099:
        return False
    prefix = text[max(0, match.start() - 2) : match.start()]
    suffix = text[match.end() : match.end() + 12].lower()
    if "$" in prefix or re.match(
        r"\s*(?:%|percent|thousand|million|billion|trillion)\b",
        suffix,
    ):
        return False
    return True


def _explicit_approximate_percentage_match(
    prediction: str,
    predicted: float,
    gold_answer: str,
    gold: float,
) -> bool:
    prediction_text = str(prediction or "")
    gold_text = str(gold_answer or "")
    if not PERCENT_RE.search(prediction_text) or not PERCENT_RE.search(gold_text):
        return False
    prediction_approximate = bool(APPROXIMATION_RE.search(prediction_text))
    gold_approximate = bool(APPROXIMATION_RE.search(gold_text))
    if not prediction_approximate and not gold_approximate:
        return False
    approximate_precisions = [
        _number_decimal_places(text)
        for text, approximate in (
            (prediction_text, prediction_approximate),
            (gold_text, gold_approximate),
        )
        if approximate
    ]
    precision = min(approximate_precisions, default=0)
    quantum = Decimal(1).scaleb(-precision)
    return Decimal(str(predicted)).quantize(
        quantum,
        rounding=ROUND_HALF_UP,
    ) == Decimal(str(gold)).quantize(quantum, rounding=ROUND_HALF_UP)


def _number_decimal_places(text: str) -> int:
    match = _selected_number_match(text)
    if match is None:
        return 0
    raw = match.group(0).replace(",", "")
    return len(raw.rsplit(".", 1)[1]) if "." in raw else 0
