from __future__ import annotations

import re
import string
from typing import Any

from ktem.docqa.evidence_text import extract_final_answer_text

from .dataset_profiles import profile_for_dataset
from .metrics import normalize_text, round_metric, token_f1_score
from .qasper_evidence import qasper_paragraph_f1
from .ragtruth_native_scores import ragtruth_native_metrics

_INLINE_CITATION_RE = re.compile(r"\[\s*\d+(?:\s*,\s*\d+)*\s*\]")
_ARTICLE_RE = re.compile(r"\b(a|an|the)\b")
_PUNCT_TABLE = str.maketrans("", "", string.punctuation)
_QASPER_BOOLEAN_ALIASES = {"true": "yes", "yes": "yes", "false": "no", "no": "no"}
_QASPER_UNANSWERABLE_ALIASES = {
    "unanswerable",
    "not answerable",
    "insufficient evidence",
    "not enough evidence",
}


def dataset_native_score_metadata(dataset_name: str) -> dict[str, Any]:
    family = profile_for_dataset(dataset_name).dataset_family
    if family == "alce" and _dataset_name_contains_qampari(dataset_name):
        return _alce_qampari_score_metadata(family)
    contracts = {
        "financebench": {
            "contract_id": "financebench_answer_correctness_v1",
            "primary_metric": "financebench_answer_score",
            "native_metrics": (
                "em",
                "numeric_match",
                "formula_match",
                "f1",
            ),
        },
        "qasper": {
            "contract_id": "qasper_answer_evidence_f1_v1",
            "primary_metric": "qasper_f1",
            "native_metrics": (
                "qasper_f1",
                "qasper_evidence_f1",
                "qasper_structure_valid",
            ),
        },
        "alce": {
            "contract_id": "alce_correctness_citation_v1",
            "primary_metric": "alce_score",
            "native_metrics": ("alce_correctness", "alce_citation_f1"),
        },
        "ragtruth": {
            "contract_id": "ragtruth_hallucination_spans_v1",
            "primary_metric": "ragtruth_hallucination_span_f1",
            "native_metrics": (
                "ragtruth_hallucination_span_precision",
                "ragtruth_hallucination_span_recall",
                "ragtruth_hallucination_span_f1",
                "ragtruth_json_valid",
                "ragtruth_positive_detected",
                "ragtruth_clean_specificity",
            ),
        },
    }
    contract = contracts.get(
        family,
        {
            "contract_id": "generic_answer_quality_v1",
            "primary_metric": "generic_f1",
            "native_metrics": ("f1",),
        },
    )
    return {
        "scoring_mode": "dataset_native_v1",
        "dataset_family": family,
        "paper_grade": False,
        **contract,
    }


def native_metrics_for_prediction(
    prediction: dict[str, Any],
    *,
    dataset_name: str,
) -> tuple[dict[str, float | None], dict[str, Any]]:
    metadata = native_score_metadata_for_prediction(
        prediction,
        dataset_name=dataset_name,
    )
    family = str(metadata["dataset_family"])
    if family == "financebench":
        metrics = _financebench_metrics(prediction)
    elif family == "qasper":
        metrics = _qasper_metrics(prediction)
    elif metadata["contract_id"] == "alce_qampari_f1_v1":
        metrics = _alce_qampari_metrics(prediction)
    elif family == "alce":
        metrics = _alce_metrics(prediction)
    elif family == "ragtruth":
        metrics = ragtruth_native_metrics(prediction)
    else:
        metrics = _generic_metrics(prediction)

    primary_metric = str(metadata["primary_metric"])
    metrics["native_score"] = metrics.get(primary_metric)
    return metrics, metadata


def native_score_metadata_for_prediction(
    prediction: dict[str, Any],
    *,
    dataset_name: str,
) -> dict[str, Any]:
    metadata = dataset_native_score_metadata(dataset_name)
    if metadata["dataset_family"] == "alce" and _is_qampari_prediction(
        prediction,
        dataset_name=dataset_name,
    ):
        return _alce_qampari_score_metadata("alce")
    return metadata


def _alce_qampari_score_metadata(family: str) -> dict[str, Any]:
    return {
        "scoring_mode": "dataset_native_v1",
        "dataset_family": family,
        "paper_grade": False,
        "contract_id": "alce_qampari_f1_v1",
        "primary_metric": "qampari_f1",
        "native_metrics": (
            "qampari_prec",
            "qampari_rec",
            "qampari_rec_top5",
            "qampari_f1",
            "qampari_f1_top5",
        ),
    }


def _financebench_metrics(prediction: dict[str, Any]) -> dict[str, float | None]:
    metrics = dict(prediction.get("metrics") or {})
    score = _max_score(
        metrics.get("em"),
        metrics.get("numeric_match"),
        metrics.get("formula_match"),
    )
    if score is None:
        score = _answer_token_f1(prediction)
    return {"financebench_answer_score": score}


def _qasper_metrics(prediction: dict[str, Any]) -> dict[str, float | None]:
    predicted_answer = _normalize_qasper_answer(_final_answer_text(prediction))
    gold_answers = [
        _normalize_qasper_answer(answer) for answer in _qasper_gold_answers(prediction)
    ]
    return {
        "qasper_f1": (
            round_metric(token_f1_score(predicted_answer, gold_answers))
            if gold_answers
            else None
        ),
        "qasper_evidence_f1": _qasper_evidence_f1(prediction),
        "qasper_structure_valid": _qasper_structure_valid(
            predicted_answer,
            gold_answers,
        ),
    }


def _qasper_structure_valid(
    predicted_answer: str,
    gold_answers: list[str],
) -> float | None:
    normalized_gold = {normalize_text(answer) for answer in gold_answers}
    normalized_prediction = normalize_text(predicted_answer)
    if normalized_gold == {"unanswerable"}:
        return float(normalized_prediction == "unanswerable")
    if normalized_gold and normalized_gold <= {"yes", "no"}:
        return float(normalized_prediction in {"yes", "no"})
    return None


def _alce_metrics(prediction: dict[str, Any]) -> dict[str, float | None]:
    base_metrics = dict(prediction.get("metrics") or {})
    correctness = _answer_correctness_score(prediction)
    citation_f1 = _f1_from_precision_recall(
        base_metrics.get("citation_precision"),
        base_metrics.get("citation_recall"),
    )
    alce_score = _mean_available(correctness, citation_f1)
    return {
        "alce_correctness": correctness,
        "alce_citation_f1": citation_f1,
        "alce_score": alce_score,
    }


def _alce_qampari_metrics(prediction: dict[str, Any]) -> dict[str, float | None]:
    predictions = _qampari_predicted_answers(prediction)
    answer_groups = _qampari_answer_groups(prediction)
    if not answer_groups:
        return {
            "qampari_num_preds": None,
            "qampari_prec": None,
            "qampari_rec": None,
            "qampari_rec_top5": None,
            "qampari_f1": None,
            "qampari_f1_top5": None,
        }

    flat_answers = {answer for group in answer_groups for answer in group}
    matches = sum(1 for item in predictions if item in flat_answers)
    covered_groups = sum(
        1 for group in answer_groups if any(answer in predictions for answer in group)
    )
    precision = matches / len(predictions) if predictions else 0.0
    recall = covered_groups / len(answer_groups)
    rec_top5 = min(5, covered_groups) / min(5, len(answer_groups))
    return {
        "qampari_num_preds": float(len(predictions)),
        "qampari_prec": round_metric(precision) or 0.0,
        "qampari_rec": round_metric(recall) or 0.0,
        "qampari_rec_top5": round_metric(rec_top5) or 0.0,
        "qampari_f1": _f1_from_precision_recall(precision, recall),
        "qampari_f1_top5": _f1_from_precision_recall(precision, rec_top5),
    }


def _generic_metrics(prediction: dict[str, Any]) -> dict[str, float | None]:
    return {"generic_f1": _answer_token_f1(prediction)}


def _answer_correctness_score(prediction: dict[str, Any]) -> float | None:
    answer = normalize_text(_final_answer_text(prediction))
    gold_answers = [
        normalize_text(answer)
        for answer in prediction.get("gold_answers", [])
        if normalize_text(answer)
    ]
    if not gold_answers:
        return None
    if answer and any(gold in answer for gold in gold_answers):
        return 1.0
    metrics = dict(prediction.get("metrics") or {})
    return _max_score(
        metrics.get("em"),
        _answer_token_f1(prediction),
        metrics.get("anls"),
        metrics.get("numeric_match"),
        metrics.get("formula_match"),
    )


def _final_answer_text(prediction: dict[str, Any]) -> str:
    if "answer_for_scoring" in prediction:
        raw_answer = prediction.get("answer_for_scoring")
    else:
        raw_answer = prediction.get("predicted_answer")
    answer = extract_final_answer_text(str(raw_answer or ""))
    return _INLINE_CITATION_RE.sub(" ", answer).strip()


def _dataset_name_contains_qampari(dataset_name: str) -> bool:
    return "qampari" in str(dataset_name or "").lower()


def _is_qampari_prediction(
    prediction: dict[str, Any],
    *,
    dataset_name: str,
) -> bool:
    metadata = dict(prediction.get("example_metadata") or {})
    task = str(metadata.get("alce_task") or metadata.get("task") or "").lower()
    answer_type = str(prediction.get("answer_type") or "").lower()
    return (
        _dataset_name_contains_qampari(dataset_name)
        or task == "qampari"
        or answer_type in {"list_qa", "list"}
    )


def _qampari_predicted_answers(prediction: dict[str, Any]) -> list[str]:
    text = _final_answer_text(prediction).rstrip().rstrip(".").rstrip(",")
    return [
        item
        for item in (_alce_normalize_answer(part.strip()) for part in text.split(","))
        if item
    ]


def _qampari_answer_groups(prediction: dict[str, Any]) -> list[list[str]]:
    metadata = dict(prediction.get("example_metadata") or {})
    groups: list[list[str]] = []
    for group in metadata.get("alce_answers") or []:
        if not isinstance(group, list):
            continue
        aliases = [
            alias
            for alias in (_alce_normalize_answer(str(item)) for item in group)
            if alias
        ]
        if aliases:
            groups.append(aliases)
    return groups


def _alce_normalize_answer(text: str) -> str:
    lowered = str(text or "").lower()
    without_punc = lowered.translate(_PUNCT_TABLE)
    without_articles = _ARTICLE_RE.sub(" ", without_punc)
    return " ".join(without_articles.split())


def _answer_token_f1(prediction: dict[str, Any]) -> float | None:
    return _token_f1_against(prediction, _prediction_gold_answers(prediction))


def _token_f1_against(
    prediction: dict[str, Any],
    gold_answers: list[str],
) -> float | None:
    if not gold_answers:
        return None
    return round_metric(token_f1_score(_final_answer_text(prediction), gold_answers))


def _prediction_gold_answers(prediction: dict[str, Any]) -> list[str]:
    return [
        str(answer)
        for answer in prediction.get("gold_answers", [])
        if str(answer or "").strip()
    ]


def _qasper_gold_answers(prediction: dict[str, Any]) -> list[str]:
    gold_answers = [
        str(answer)
        for answer in prediction.get("gold_answers", [])
        if str(answer or "").strip()
    ]
    if gold_answers:
        return gold_answers
    metadata = dict(prediction.get("example_metadata") or {})
    annotations = metadata.get("qasper_answer_annotations")
    if not isinstance(annotations, list):
        return []
    return _normalized_nonempty_strings(
        [
            answer
            for annotation in annotations
            if isinstance(annotation, dict)
            for answer in _qasper_annotation_answers(annotation)
        ]
    )


def _qasper_annotation_answers(annotation: dict[str, Any]) -> list[str]:
    if annotation.get("unanswerable"):
        return ["unanswerable"]
    yes_no = annotation.get("yes_no")
    if yes_no is not None:
        return ["yes" if bool(yes_no) else "no"]
    answers = [
        str(item).strip()
        for item in annotation.get("extractive_spans", [])
        if str(item).strip()
    ]
    free_form = str(annotation.get("free_form_answer") or "").strip()
    if free_form:
        answers.append(free_form)
    return answers


def _normalize_qasper_answer(answer: str) -> str:
    normalized = normalize_text(answer)
    if normalized in _QASPER_UNANSWERABLE_ALIASES:
        return "unanswerable"
    return _QASPER_BOOLEAN_ALIASES.get(normalized, str(answer or ""))


def _qasper_evidence_f1(prediction: dict[str, Any]) -> float | None:
    gold_references = _qasper_gold_evidence_references(prediction)
    if not gold_references:
        return None
    predicted_evidence = _qasper_predicted_evidence(prediction)
    return round_metric(
        max(
            qasper_paragraph_f1(predicted_evidence, reference)
            for reference in gold_references
        )
    )


def _qasper_gold_evidence_references(
    prediction: dict[str, Any],
) -> list[list[str]]:
    metadata = dict(prediction.get("example_metadata") or {})
    annotations = metadata.get("qasper_answer_annotations")
    references: list[list[str]] = []
    if isinstance(annotations, list):
        for annotation in annotations:
            if not isinstance(annotation, dict):
                continue
            evidence = _nonempty_strings(annotation.get("evidence"))
            if annotation.get("unanswerable") and not evidence:
                references.append([])
            elif evidence:
                references.append(evidence)
    if references:
        return references

    gold_evidence = prediction.get("gold_evidence")
    if isinstance(gold_evidence, list):
        evidence = [
            text
            for item in gold_evidence
            if isinstance(item, dict)
            for text in _nonempty_strings(
                item.get("span") or item.get("text") or item.get("evidence")
            )
        ]
        if evidence:
            return [evidence]
    return []


def _qasper_predicted_evidence(prediction: dict[str, Any]) -> list[str]:
    explicit_evidence = _nonempty_strings(prediction.get("predicted_evidence"))
    if explicit_evidence:
        return explicit_evidence

    evidence: list[str] = []
    for key in ("retrieved_hits",):
        records = prediction.get(key)
        if not isinstance(records, list):
            continue
        for record in records:
            if isinstance(record, dict):
                evidence.extend(
                    _nonempty_strings(
                        record.get("text")
                        or record.get("snippet")
                        or record.get("caption")
                        or record.get("ocr_text")
                    )
                )
    return evidence


def _nonempty_strings(value: Any) -> list[str]:
    return [text for text in (str(item).strip() for item in _as_list(value)) if text]


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _normalized_nonempty_strings(values: list[Any]) -> list[str]:
    return [value for value in (normalize_text(str(item)) for item in values) if value]


def _f1_from_precision_recall(precision: Any, recall: Any) -> float | None:
    precision_score = _score(precision)
    recall_score = _score(recall)
    if precision_score is None or recall_score is None:
        return None
    if precision_score + recall_score == 0.0:
        return 0.0
    return round_metric(
        2 * precision_score * recall_score / (precision_score + recall_score)
    )


def _mean_available(*values: Any) -> float | None:
    scores = [_score(value) for value in values]
    usable_scores = [score for score in scores if score is not None]
    if not usable_scores:
        return None
    return round_metric(sum(usable_scores) / len(usable_scores))


def _max_score(*values: Any) -> float | None:
    scores = [_score(value) for value in values]
    usable_scores = [score for score in scores if score is not None]
    if not usable_scores:
        return None
    return round_metric(max(usable_scores))


def _score(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)
