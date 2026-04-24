from __future__ import annotations

import math
import re
import string
from collections import Counter
from statistics import mean

PUNCT_TABLE = str.maketrans("", "", string.punctuation)
WHITESPACE_RE = re.compile(r"\s+")
NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")
ABSTENTION_RE = re.compile(
    "|".join(
        [
            r"文档证据无法支持",
            r"证据无法支持",
            r"无法根据(?:所给|当前)?文档",
            r"没有足够(?:的)?(?:文档)?证据",
            r"insufficient evidence",
            r"not enough evidence",
            r"not supported by (?:the )?document",
            r"cannot be supported by (?:the )?document",
            r"cannot answer (?:from|based on)",
            r"unable to answer (?:from|based on)",
        ]
    ),
    flags=re.IGNORECASE,
)
TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$")
LATEX_SIGNAL_RE = re.compile(
    r"(\\[a-zA-Z]+|[_^]\s*\{?[\w+\-=]+|[A-Za-z0-9]\s*[_^]\s*\{)"
)
LATEX_DELIMITED_RE = re.compile(
    r"(\$\$.*?\$\$|\$[^$\n]+?\$|\\\(.*?\\\)|\\\[.*?\\\])",
    flags=re.DOTALL,
)


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


def _gold_values_from_evidence(
    gold_evidence: list[dict[str, object]],
    key: str,
) -> list[str]:
    return [
        str(item[key]).strip()
        for item in gold_evidence
        if str(item.get(key) or "").strip()
    ]


def element_hit_score(
    predicted_element_ids: list[str],
    gold_evidence: list[dict[str, object]],
) -> float | None:
    gold_element_ids = _gold_values_from_evidence(gold_evidence, "element_id")
    if not gold_element_ids:
        return None
    predicted = {
        str(element_id).strip()
        for element_id in predicted_element_ids
        if str(element_id).strip()
    }
    return float(bool(predicted & set(gold_element_ids)))


def span_recall_score(
    predicted_text: str,
    gold_evidence: list[dict[str, object]],
) -> float | None:
    gold_spans = _gold_values_from_evidence(gold_evidence, "span")
    if not gold_spans:
        return None
    normalized_prediction = normalize_text(predicted_text)
    if not normalized_prediction:
        return 0.0
    hits = sum(
        1 for span in gold_spans if normalize_text(span) in normalized_prediction
    )
    return hits / len(gold_spans)


def citation_recall_score(
    predicted_citations: list[str],
    gold_evidence: list[dict[str, object]],
) -> float | None:
    return recall_score(
        predicted_citations,
        _gold_values_from_evidence(gold_evidence, "citation"),
    )


def _normalize_formula(text: str) -> str:
    formula = str(text or "").strip().lower()
    if formula.startswith("="):
        formula = formula[1:]
    return WHITESPACE_RE.sub("", formula)


def formula_normalized_match_score(
    prediction: str,
    gold_answers: list[str],
) -> float:
    normalized_prediction = _normalize_formula(prediction)
    if not normalized_prediction or not gold_answers:
        return 0.0
    return float(
        any(
            normalized_prediction == _normalize_formula(answer)
            for answer in gold_answers
        )
    )


def _extract_number(text: str) -> float | None:
    match = NUMBER_RE.search(str(text or ""))
    if not match:
        return None
    return float(match.group(0).replace(",", ""))


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
    return 0.0


def is_abstention_answer(prediction: str) -> bool:
    return bool(ABSTENTION_RE.search(str(prediction or "")))


def false_abstention_score(prediction: str, gold_answers: list[str]) -> float:
    has_gold_answer = any(str(answer or "").strip() for answer in gold_answers)
    return float(has_gold_answer and is_abstention_answer(prediction))


def _split_markdown_table_row(line: str) -> list[str]:
    row = line.strip()
    if row.startswith("|"):
        row = row[1:]
    if row.endswith("|"):
        row = row[:-1]
    return [cell.strip() for cell in row.split("|")]


def markdown_table_renderable_score(prediction: str) -> float | None:
    lines = [
        line.rstrip()
        for line in str(prediction or "").splitlines()
        if "|" in line and line.strip()
    ]
    if not lines:
        return None

    table_like = False
    for index in range(len(lines) - 1):
        header = lines[index]
        separator = lines[index + 1]
        if header.count("|") < 2:
            continue
        table_like = True
        if not TABLE_SEPARATOR_RE.match(separator):
            continue
        header_cells = _split_markdown_table_row(header)
        separator_cells = _split_markdown_table_row(separator)
        if len(header_cells) >= 2 and len(header_cells) == len(separator_cells):
            return 1.0

    return 0.0 if table_like else None


def latex_renderable_score(prediction: str) -> float | None:
    text = str(prediction or "")
    if not LATEX_SIGNAL_RE.search(text):
        return None
    for match in LATEX_DELIMITED_RE.finditer(text):
        if LATEX_SIGNAL_RE.search(match.group(0)):
            return 1.0
    return 0.0


def safe_mean(values: list[float | None]) -> float | None:
    usable = [value for value in values if value is not None]
    if not usable:
        return None
    return mean(usable)


def round_metric(value: float | None, digits: int = 4) -> float | None:
    if value is None or math.isnan(value):
        return None
    return round(value, digits)
