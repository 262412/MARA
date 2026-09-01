from __future__ import annotations

from collections import Counter
from typing import Any

from ktem.docqa.qasper_boolean_no_evidence import qasper_no_evidence_set_analysis

from .metrics import normalize_text, round_metric, token_f1_score
from .qasper_evidence import qasper_paragraph_f1


def qasper_annotation_diagnostics(
    prediction: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Score each QASPER annotation independently without changing official score."""

    from . import dataset_native_scores as native_scores

    metadata = dict(prediction.get("example_metadata") or {})
    annotations = metadata.get("qasper_answer_annotations")
    if not isinstance(annotations, list):
        return [], _diagnostics_summary([], [])
    predicted_answer = native_scores._normalize_qasper_answer(
        native_scores._final_answer_text(prediction)
    )
    predicted_evidence = native_scores._qasper_predicted_evidence(prediction)
    question = str(prediction.get("question") or "")
    rows = [
        _annotation_row(
            index,
            raw,
            question,
            predicted_answer,
            predicted_evidence,
            native_scores,
        )
        for index, raw in enumerate(annotations, start=1)
        if isinstance(raw, dict)
    ]
    reasons = _ambiguity_reasons(rows)
    marker = ",".join(reasons)
    if marker:
        for row in rows:
            row["ambiguity_marker"] = marker
    return rows, _diagnostics_summary(rows, reasons)


def _annotation_row(
    index: int,
    annotation: dict[str, Any],
    question: str,
    predicted_answer: str,
    predicted_evidence: list[str],
    native_scores: Any,
) -> dict[str, Any]:
    answers = [
        native_scores._normalize_qasper_answer(answer)
        for answer in native_scores._qasper_annotation_answers(annotation)
    ]
    normalized_answers = native_scores._normalized_nonempty_strings(answers)
    answer_type = _answer_type(annotation, normalized_answers)
    answer_class = tuple(sorted(set(normalized_answers)))
    evidence = native_scores._nonempty_strings(annotation.get("evidence"))
    typed = bool(answer_class) and set(answer_class) <= {
        "yes",
        "no",
        "unanswerable",
    }
    no_evidence_semantics = (
        qasper_no_evidence_set_analysis(question, evidence)
        if answer_class == ("no",)
        else {}
    )
    return {
        "contract_id": "qasper_annotation_score.v1",
        "annotation_index": index,
        "annotation_id": str(annotation.get("annotation_id") or f"annotation:{index}"),
        "worker_id": str(annotation.get("worker_id") or ""),
        "answer_type": answer_type,
        "answers": answers,
        "normalized_answers": normalized_answers,
        "predicted_answer": predicted_answer,
        "answer_f1": _answer_f1(predicted_answer, normalized_answers),
        "typed_accuracy": _typed_accuracy(predicted_answer, answer_class, typed),
        "evidence_f1": _evidence_f1(
            predicted_evidence,
            evidence,
            bool(annotation.get("unanswerable")),
        ),
        "annotation_answer_class": list(answer_class),
        "no_evidence_semantics": no_evidence_semantics,
        "ambiguity_marker": "",
    }


def _answer_f1(predicted_answer: str, answers: list[str]) -> float | None:
    if not answers:
        return None
    return round_metric(token_f1_score(predicted_answer, answers))


def _typed_accuracy(
    predicted_answer: str,
    answer_class: tuple[str, ...],
    typed: bool,
) -> float | None:
    if not typed:
        return None
    return float(normalize_text(predicted_answer) in set(answer_class))


def _evidence_f1(
    predicted_evidence: list[str],
    evidence: list[str],
    unanswerable: bool,
) -> float | None:
    if not evidence and not unanswerable:
        return None
    return round_metric(qasper_paragraph_f1(predicted_evidence, evidence))


def _answer_type(annotation: dict[str, Any], answers: list[str]) -> str:
    if annotation.get("unanswerable"):
        return "unanswerable"
    if annotation.get("yes_no") is not None:
        return "boolean"
    if annotation.get("extractive_spans"):
        return "extractive"
    if annotation.get("free_form_answer"):
        return "free_text"
    return "empty" if not answers else "free_text"


def _ambiguity_reasons(rows: list[dict[str, Any]]) -> list[str]:
    classes = {tuple(row.get("annotation_answer_class") or []) for row in rows}
    answer_types = {str(row.get("answer_type") or "") for row in rows}
    reasons: list[str] = []
    if len(classes) > 1:
        reasons.append("annotation_answer_disagreement")
    if len(answer_types) > 1:
        reasons.append("annotation_type_disagreement")
    if any(
        dict(row.get("no_evidence_semantics") or {}).get("annotation_contract_status")
        == "ambiguous_no_evidence_semantics"
        for row in rows
    ):
        reasons.append("boolean_no_requires_closed_world_inference")
    return reasons


def _diagnostics_summary(
    rows: list[dict[str, Any]],
    reasons: list[str],
) -> dict[str, Any]:
    answer_classes = sorted({tuple(row["annotation_answer_class"]) for row in rows})
    no_semantics = Counter(
        str(value.get("classification") or "")
        for row in rows
        if (value := dict(row.get("no_evidence_semantics") or {}))
    )
    return {
        "contract_id": "qasper_annotation_diagnostics.v1",
        "annotation_count": len(rows),
        "ambiguous": bool(reasons),
        "ambiguity_reasons": reasons,
        "canonical_answer_classes": [list(value) for value in answer_classes],
        "boolean_no_evidence_semantics": dict(sorted(no_semantics.items())),
    }
