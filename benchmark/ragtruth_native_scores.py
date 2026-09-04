from __future__ import annotations

import json
import re
from typing import Any

from ktem.docqa.evidence_text import extract_final_answer_text

from .metrics import normalize_text, round_metric, token_f1_score

_INLINE_CITATION_RE = re.compile(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]")

_RAGTRUTH_TASK_FAMILIES = {
    "ragtruth",
    "hallucination_guardrail",
    "hallucination_verification",
}


def is_ragtruth_prediction(prediction: dict[str, Any]) -> bool:
    metadata = dict(prediction.get("example_metadata") or {})
    candidates = (
        prediction.get("dataset_family"),
        metadata.get("dataset_family"),
        prediction.get("dataset_name"),
        metadata.get("dataset_name"),
    )
    for candidate in candidates:
        normalized = str(candidate or "").strip().lower().replace("-", "_")
        if normalized in _RAGTRUTH_TASK_FAMILIES or normalized.startswith("ragtruth_"):
            return True
    return False


def ragtruth_native_objective(prediction: dict[str, Any]) -> float | None:
    """Return the native hallucination score when it is available.

    Raw answers are evaluated first so generic QA metrics cannot override the
    task contract. Predictions that have already been rescored can fall back
    to their persisted native fields.
    """

    computed = ragtruth_native_metrics(prediction)
    if computed["ragtruth_json_valid"] == 0.0:
        return 0.0
    if (
        computed["ragtruth_json_valid"] == 1.0
        and _explicit_label_list(prediction) is not None
    ):
        return computed["ragtruth_hallucination_span_f1"]

    metrics = dict(prediction.get("metrics") or {})
    for key in ("ragtruth_hallucination_span_f1", "native_score"):
        if key not in metrics:
            continue
        try:
            return float(metrics[key])
        except (TypeError, ValueError):
            continue
    if metrics.get("ragtruth_json_valid") is not None:
        try:
            if float(metrics["ragtruth_json_valid"]) == 0.0:
                return 0.0
        except (TypeError, ValueError):
            pass
    return None


def _explicit_label_list(prediction: dict[str, Any]) -> list[Any] | None:
    metadata = dict(prediction.get("example_metadata") or {})
    if "labels" not in metadata and "hallucination_labels" not in metadata:
        return None

    labels = metadata.get("labels")
    if labels:
        return labels if isinstance(labels, list) else None
    hallucination_labels = metadata.get("hallucination_labels")
    if hallucination_labels is not None:
        return hallucination_labels if isinstance(hallucination_labels, list) else None
    return labels if isinstance(labels, list) else None


def ragtruth_native_metrics(
    prediction: dict[str, Any],
) -> dict[str, float | None]:
    json_valid = _json_valid(prediction)
    predicted_spans = _predicted_spans(prediction)
    gold_spans = _gold_spans(prediction)
    precision, recall, span_f1 = _span_set_scores(predicted_spans, gold_spans)
    if json_valid is False:
        precision = recall = span_f1 = 0.0
    return {
        "ragtruth_hallucination_span_precision": precision,
        "ragtruth_hallucination_span_recall": recall,
        "ragtruth_hallucination_span_f1": span_f1,
        "ragtruth_json_valid": None if json_valid is None else float(json_valid),
        "ragtruth_positive_detected": (
            float(bool(json_valid) and bool(predicted_spans))
            if gold_spans and json_valid is not None
            else None
        ),
        "ragtruth_clean_specificity": (
            float(bool(json_valid) and not predicted_spans)
            if not gold_spans and json_valid is not None
            else None
        ),
    }


def _predicted_spans(prediction: dict[str, Any]) -> list[str]:
    parsed = _parse_json_answer(_final_answer_text(prediction))
    if isinstance(parsed, dict):
        for key in ("hallucination list", "hallucinations", "hallucination_spans"):
            values = parsed.get(key)
            if isinstance(values, list):
                return _normalized_nonempty_strings(values)
    if isinstance(parsed, list):
        return _normalized_nonempty_strings(parsed)
    return []


def _json_valid(prediction: dict[str, Any]) -> bool | None:
    if "answer_for_scoring" not in prediction and "predicted_answer" not in prediction:
        return None
    parsed = _parse_json_answer(_final_answer_text(prediction))
    if not isinstance(parsed, dict) or set(parsed) != {"hallucination list"}:
        return False
    values = parsed.get("hallucination list")
    return isinstance(values, list) and all(isinstance(value, str) for value in values)


def _gold_spans(prediction: dict[str, Any]) -> list[str]:
    metadata = dict(prediction.get("example_metadata") or {})
    labels = metadata.get("labels") or metadata.get("hallucination_labels") or []
    spans: list[str] = []
    if isinstance(labels, list):
        for label in labels:
            if not isinstance(label, dict) or not _is_hallucination_label(label):
                continue
            span = _first_text_value(
                label,
                ("text", "span", "hallucination_span", "value", "label_text"),
            )
            if span:
                spans.append(span)
    return _normalized_nonempty_strings(spans)


def _is_hallucination_label(label: dict[str, Any]) -> bool:
    label_kind = normalize_text(
        label.get("label_type")
        or label.get("type")
        or label.get("category")
        or label.get("label")
        or ""
    )
    if not label_kind:
        return True
    if any(term in label_kind for term in ("supported", "nonhallucination")):
        return False
    return any(
        term in label_kind
        for term in ("hallucination", "baseless", "conflict", "unsupported")
    )


def _span_set_scores(
    predicted_spans: list[str],
    gold_spans: list[str],
) -> tuple[float, float, float]:
    if not predicted_spans and not gold_spans:
        return 1.0, 1.0, 1.0
    if not gold_spans:
        return 0.0, 1.0, 0.0
    if not predicted_spans:
        return 1.0, 0.0, 0.0

    matches = _count_span_matches(predicted_spans, gold_spans)
    if matches == 0:
        return 0.0, 0.0, 0.0
    precision = matches / len(predicted_spans)
    recall = matches / len(gold_spans)
    span_f1 = 2 * precision * recall / (precision + recall)
    return (
        round_metric(precision) or 0.0,
        round_metric(recall) or 0.0,
        round_metric(span_f1) or 0.0,
    )


def _count_span_matches(predicted_spans: list[str], gold_spans: list[str]) -> int:
    used_gold_indexes: set[int] = set()
    matches = 0
    for predicted_span in predicted_spans:
        for index, gold_span in enumerate(gold_spans):
            if index in used_gold_indexes or not _spans_match(
                predicted_span, gold_span
            ):
                continue
            used_gold_indexes.add(index)
            matches += 1
            break
    return matches


def _spans_match(predicted_span: str, gold_span: str) -> bool:
    return bool(
        predicted_span == gold_span
        or predicted_span in gold_span
        or gold_span in predicted_span
        or token_f1_score(predicted_span, [gold_span]) >= 0.5
    )


def _final_answer_text(prediction: dict[str, Any]) -> str:
    raw_answer = (
        prediction.get("answer_for_scoring")
        if "answer_for_scoring" in prediction
        else prediction.get("predicted_answer")
    )
    answer = extract_final_answer_text(str(raw_answer or ""))
    return _INLINE_CITATION_RE.sub(" ", answer).strip()


def _parse_json_answer(answer: str) -> Any:
    try:
        return json.loads(str(answer or "").strip())
    except (json.JSONDecodeError, TypeError):
        return None


def _first_text_value(item: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return ""


def _normalized_nonempty_strings(values: list[Any]) -> list[str]:
    return [value for value in (normalize_text(str(item)) for item in values) if value]
