from __future__ import annotations

import math
import re
import string
from collections import Counter
from statistics import mean

PUNCT_TABLE = str.maketrans("", "", string.punctuation)
WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    text = str(text or "").lower().translate(PUNCT_TABLE)
    text = WHITESPACE_RE.sub(" ", text)
    return text.strip()


def _tokenize(text: str) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    if " " in normalized:
        return normalized.split()
    return list(normalized)


def exact_match_score(prediction: str, gold_answers: list[str]) -> float:
    normalized_prediction = normalize_text(prediction)
    if not gold_answers:
        return 0.0
    return float(
        any(normalized_prediction == normalize_text(answer) for answer in gold_answers)
    )


def token_f1_score(prediction: str, gold_answers: list[str]) -> float:
    if not gold_answers:
        return 0.0

    pred_tokens = _tokenize(prediction)
    if not pred_tokens:
        return 0.0

    best_score = 0.0
    pred_counter = Counter(pred_tokens)
    for answer in gold_answers:
        gold_tokens = _tokenize(answer)
        if not gold_tokens:
            continue
        gold_counter = Counter(gold_tokens)
        common = sum((pred_counter & gold_counter).values())
        if common == 0:
            continue
        precision = common / len(pred_tokens)
        recall = common / len(gold_tokens)
        score = 2 * precision * recall / (precision + recall)
        best_score = max(best_score, score)
    return best_score


def _levenshtein_distance(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)

    previous = list(range(len(right) + 1))
    for left_index, left_char in enumerate(left, start=1):
        current = [left_index]
        for right_index, right_char in enumerate(right, start=1):
            insert_cost = current[right_index - 1] + 1
            delete_cost = previous[right_index] + 1
            replace_cost = previous[right_index - 1] + (left_char != right_char)
            current.append(min(insert_cost, delete_cost, replace_cost))
        previous = current
    return previous[-1]


def anls_score(
    prediction: str, gold_answers: list[str], threshold: float = 0.5
) -> float:
    if not gold_answers:
        return 0.0

    normalized_prediction = normalize_text(prediction)
    if not normalized_prediction:
        return 0.0

    best_score = 0.0
    for answer in gold_answers:
        normalized_answer = normalize_text(answer)
        if not normalized_answer:
            continue
        distance = _levenshtein_distance(normalized_prediction, normalized_answer)
        normalized_distance = distance / max(
            len(normalized_prediction), len(normalized_answer), 1
        )
        similarity = 1.0 - normalized_distance
        if similarity >= threshold:
            best_score = max(best_score, similarity)
    return max(best_score, 0.0)


def page_hit_score(
    predicted_pages: list[int | str],
    gold_pages: list[int | str],
) -> float | None:
    if not gold_pages:
        return None
    predicted = {str(page) for page in predicted_pages}
    gold = {str(page) for page in gold_pages}
    return float(bool(predicted & gold))


def recall_score(predicted_items: list[str], gold_items: list[str]) -> float | None:
    if not gold_items:
        return None
    predicted = {str(item).strip() for item in predicted_items if str(item).strip()}
    gold = {str(item).strip() for item in gold_items if str(item).strip()}
    if not gold:
        return None
    return len(predicted & gold) / len(gold)


def safe_mean(values: list[float | None]) -> float | None:
    usable = [value for value in values if value is not None]
    if not usable:
        return None
    return mean(usable)


def round_metric(value: float | None, digits: int = 4) -> float | None:
    if value is None or math.isnan(value):
        return None
    return round(value, digits)
