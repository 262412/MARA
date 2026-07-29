from __future__ import annotations

import math
import re
import string
import unicodedata
from collections import Counter
from collections.abc import Callable
from statistics import mean

PUNCT_TABLE = str.maketrans("", "", string.punctuation)
WHITESPACE_RE = re.compile(r"\s+")
NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")
ABSTENTION_RE = re.compile(
    r"^\s*(?:"
    r"unanswerable\b.*|"
    r"MARA could not retrieve enough evidence\b.*|"
    r"(?:the\s+)?(?:available\s+)?(?:document\s+)?evidence is insufficient\b.*|"
    r"insufficient evidence\b.*|"
    r"not enough evidence\b.*|"
    r"not supported by (?:the )?document\b.*|"
    r"cannot be supported by (?:the )?document\b.*|"
    r"cannot answer\b.*|"
    r"unable to answer\b.*|"
    r"文档证据无法支持(?:该回答|这个回答|回答该问题)?[。.!！]?\s*|"
    r"证据无法支持(?:该回答|这个回答|回答该问题)?[。.!！]?\s*|"
    r"无法根据(?:所给|当前|现有|可用)?文档(?:证据)?(?:回答|作答).+|"
    r"(?:当前|现有|可用)?文档没有足够(?:的)?证据(?:回答|支持).+|"
    r"没有足够(?:的)?(?:文档)?证据(?:回答|支持).+"
    r")\s*$",
    flags=re.IGNORECASE | re.DOTALL,
)
TOKEN_V2_RE = re.compile(
    r"[$€£¥]?\d+(?:[.,]\d+)*(?:%)?|"
    r"[a-z]+(?:['’][a-z]+)?|"
    r"[\u3400-\u4dbf\u4e00-\u9fff]",
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


def _legacy_tokenize(text: str) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    if " " in normalized:
        return normalized.split()
    return list(normalized)


def _tokenize(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", str(text or "")).lower()
    return [match.group(0) for match in TOKEN_V2_RE.finditer(normalized)]


def exact_match_score(prediction: str, gold_answers: list[str]) -> float:
    normalized_prediction = normalize_text(prediction)
    if not gold_answers:
        return 0.0
    return float(
        any(normalized_prediction == normalize_text(answer) for answer in gold_answers)
    )


def legacy_token_f1_score(prediction: str, gold_answers: list[str]) -> float:
    return _token_f1(
        prediction,
        gold_answers,
        tokenizer=_legacy_tokenize,
    )


def token_f1_score(prediction: str, gold_answers: list[str]) -> float:
    return _token_f1(prediction, gold_answers, tokenizer=_tokenize)


def _token_f1(
    prediction: str,
    gold_answers: list[str],
    *,
    tokenizer: Callable[[str], list[str]],
) -> float:
    if not gold_answers:
        return 0.0

    pred_tokens = tokenizer(prediction)
    if not pred_tokens:
        return 0.0

    best_score = 0.0
    pred_counter = Counter(pred_tokens)
    for answer in gold_answers:
        gold_tokens = tokenizer(answer)
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


def _modality_tokens(*values: object) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        text = str(value or "").strip().lower().replace("-", "_")
        if not text:
            continue
        tokens.add(text)
        tokens.update(item for item in re.split(r"[^a-z0-9_]+", text) if item)
    return tokens


def _gold_evidence_modalities(gold_evidence: list[dict[str, object]]) -> set[str]:
    keys = ("modality", "element_type", "type", "kind", "category", "content_type")
    return {
        token
        for item in gold_evidence
        for key in keys
        for token in _modality_tokens(item.get(key))
    }


def _contains_modality(tokens: set[str], target: str) -> bool:
    return any(token == target or token.startswith(f"{target}_") for token in tokens)


def modality_hit_score(
    modality: str,
    *,
    expected_modality: str,
    evidence_metadata: dict[str, object],
    retrieved_hits: list[dict[str, object]],
    gold_evidence: list[dict[str, object]],
) -> float | None:
    target = str(modality or "").strip().lower().replace("-", "_")
    expected = _modality_tokens(expected_modality)
    gold_modalities = _gold_evidence_modalities(gold_evidence)
    if not _contains_modality(expected | gold_modalities, target):
        return None

    if bool(evidence_metadata.get(f"has_{target}_evidence")):
        return 1.0
    modality_counts = evidence_metadata.get("modality_counts")
    if isinstance(modality_counts, dict) and int(modality_counts.get(target) or 0) > 0:
        return 1.0

    for hit in retrieved_hits:
        hit_tokens = _modality_tokens(
            hit.get("modality"),
            hit.get("element_type"),
            hit.get("type"),
            hit.get("kind"),
        )
        if _contains_modality(hit_tokens, target):
            return 1.0
    return 0.0


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


def image_quote_hit_score(
    predicted_text: str,
    gold_evidence: list[dict[str, object]],
) -> float | None:
    image_quotes = [
        str(item.get("image_quote") or item.get("visual_quote") or "").strip()
        for item in gold_evidence
        if _contains_modality(
            _modality_tokens(
                item.get("modality"),
                item.get("element_type"),
                item.get("type"),
            ),
            "page_image",
        )
        or _contains_modality(
            _modality_tokens(
                item.get("modality"),
                item.get("element_type"),
                item.get("type"),
            ),
            "figure",
        )
    ]
    image_quotes = [quote for quote in image_quotes if quote]
    if not image_quotes:
        return None
    normalized_prediction = normalize_text(predicted_text)
    if not normalized_prediction:
        return 0.0
    hits = sum(
        1 for quote in image_quotes if normalize_text(quote) in normalized_prediction
    )
    return hits / len(image_quotes)


def multimodal_support_score(
    *,
    evidence_bundle: dict[str, object],
    retrieved_hits: list[dict[str, object]],
    gold_evidence: list[dict[str, object]],
) -> float | None:
    gold_modalities = _gold_evidence_modalities(gold_evidence) - {"text"}
    if not gold_modalities:
        return None
    predicted_modalities = _predicted_evidence_modalities(
        evidence_bundle, retrieved_hits
    )
    if not predicted_modalities:
        return 0.0
    hits = sum(
        1
        for modality in gold_modalities
        if _contains_modality(predicted_modalities, modality)
    )
    return hits / len(gold_modalities)


def hard_negative_rejection_score(
    *,
    retrieved_hits: list[dict[str, object]],
    evidence_bundle: dict[str, object],
    gold_evidence: list[dict[str, object]],
) -> float | None:
    hard_negative_ids = _hard_negative_ids(gold_evidence)
    if not hard_negative_ids:
        return None
    predicted_ids = _predicted_evidence_ids(evidence_bundle, retrieved_hits)
    return float(not (predicted_ids & hard_negative_ids))


def cross_page_evidence_hit_score(
    predicted_pages: list[int | str],
    *,
    evidence_bundle: dict[str, object],
    retrieved_hits: list[dict[str, object]],
    gold_evidence: list[dict[str, object]],
) -> float | None:
    gold_pages = _gold_evidence_pages(gold_evidence)
    if len(gold_pages) < 2:
        return None
    predicted = {str(page) for page in predicted_pages if str(page).strip()}
    predicted.update(_predicted_pages_from_evidence(evidence_bundle, retrieved_hits))
    return float(len(predicted & gold_pages) >= min(2, len(gold_pages)))


def _normalize_formula(text: str) -> str:
    formula = str(text or "").strip().lower()
    if formula.startswith("="):
        formula = formula[1:]
    return WHITESPACE_RE.sub("", formula)


def _predicted_evidence_modalities(
    evidence_bundle: dict[str, object],
    retrieved_hits: list[dict[str, object]],
) -> set[str]:
    bundle_items = (
        evidence_bundle.get("items") if isinstance(evidence_bundle, dict) else []
    )
    evidence_items = bundle_items if isinstance(bundle_items, list) else []
    return {
        token
        for item in [*evidence_items, *retrieved_hits]
        if isinstance(item, dict)
        for token in _modality_tokens(
            item.get("modality"),
            item.get("element_type"),
            item.get("type"),
            item.get("kind"),
        )
    }


def _hard_negative_ids(gold_evidence: list[dict[str, object]]) -> set[str]:
    ids: set[str] = set()
    for item in gold_evidence:
        for key in ("hard_negative_id", "hard_negative_evidence_id"):
            value = str(item.get(key) or "").strip()
            if value:
                ids.add(value)
        hard_negative_ids = item.get("hard_negative_ids")
        if isinstance(hard_negative_ids, list):
            ids.update(str(value).strip() for value in hard_negative_ids)
    return {item for item in ids if item}


def _predicted_evidence_ids(
    evidence_bundle: dict[str, object],
    retrieved_hits: list[dict[str, object]],
) -> set[str]:
    bundle_items = (
        evidence_bundle.get("items") if isinstance(evidence_bundle, dict) else []
    )
    evidence_items = bundle_items if isinstance(bundle_items, list) else []
    return {
        str(value).strip()
        for item in [*evidence_items, *retrieved_hits]
        if isinstance(item, dict)
        for value in (
            item.get("evidence_id"),
            item.get("doc_id"),
            item.get("element_id"),
            item.get("source_id"),
        )
        if str(value or "").strip()
    }


def _gold_evidence_pages(gold_evidence: list[dict[str, object]]) -> set[str]:
    pages = set(_gold_values_from_evidence(gold_evidence, "page"))
    pages.update(_gold_values_from_evidence(gold_evidence, "page_label"))
    for citation in _gold_values_from_evidence(gold_evidence, "citation"):
        if "#page:" in citation:
            pages.add(citation.rsplit("#page:", 1)[-1])
    return {str(page).strip() for page in pages if str(page).strip()}


def _predicted_pages_from_evidence(
    evidence_bundle: dict[str, object],
    retrieved_hits: list[dict[str, object]],
) -> set[str]:
    bundle_items = (
        evidence_bundle.get("items") if isinstance(evidence_bundle, dict) else []
    )
    pages: set[str] = set()
    for item in [
        *(bundle_items if isinstance(bundle_items, list) else []),
        *retrieved_hits,
    ]:
        if not isinstance(item, dict):
            continue
        page = str(item.get("page_label") or item.get("page") or "").strip()
        if page:
            pages.add(page)
    return pages


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
    value = str(text or "")
    matches = list(NUMBER_RE.finditer(value))
    if not matches:
        return None
    selected = next(
        (match for match in matches if not _looks_like_year(value, match)),
        matches[0],
    )
    return float(selected.group(0).replace(",", ""))


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
    has_answerable_gold = any(
        str(answer or "").strip() and not is_abstention_answer(str(answer))
        for answer in gold_answers
    )
    return float(has_answerable_gold and is_abstention_answer(prediction))


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
