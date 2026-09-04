from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import ensure_list, load_json, materialize_text_document, write_v2_manifest


def normalize_qasper_manifest(
    source_path: str | Path,
    output_path: str | Path,
) -> Path:
    papers = load_json(source_path)
    documents: list[dict[str, Any]] = []
    examples: list[dict[str, Any]] = []

    for paper_id, paper in sorted(dict(papers).items()):
        document_id = str(paper_id)
        document_path = materialize_text_document(
            output_path,
            document_id,
            _paper_text(dict(paper)),
        )
        documents.append(
            {
                "document_id": document_id,
                "path": str(document_path),
                "format_type": "txt",
                "modality": "text",
                "metadata": {
                    "title": paper.get("title"),
                    "dataset_family": "scientific_qa",
                },
            }
        )
        for index, qa in enumerate(ensure_list(paper.get("qas"))):
            if isinstance(qa, dict):
                examples.append(_example(document_id, qa, index))

    return write_v2_manifest(
        output_path,
        dataset_name="qasper",
        documents=documents,
        examples=examples,
    )


def _paper_text(paper: dict[str, Any]) -> str:
    parts = [f"# {paper.get('title', '')}".strip(), str(paper.get("abstract") or "")]
    for section in ensure_list(paper.get("full_text")):
        if not isinstance(section, dict):
            continue
        section_name = str(section.get("section_name") or "").strip()
        if section_name:
            parts.append(f"## {section_name}")
        parts.extend(str(item) for item in ensure_list(section.get("paragraphs")))
    figures = [
        value
        for value in ensure_list(paper.get("figures_and_tables"))
        if isinstance(value, dict) and str(value.get("caption") or "").strip()
    ]
    if figures:
        parts.append("## Figures and Tables")
    for figure in figures:
        file_name = str(figure.get("file") or "").strip()
        if file_name:
            parts.append(f"### {file_name}")
        caption = str(figure.get("caption") or "").strip()
        parts.append(
            caption
            if caption.startswith("FLOAT SELECTED:")
            else f"FLOAT SELECTED: {caption}"
        )
    return "\n\n".join(part for part in parts if part)


def _example(document_id: str, qa: dict[str, Any], index: int) -> dict[str, Any]:
    answers, evidence, answer_annotations = _answers_evidence_and_annotations(qa)
    answer_type = _qasper_answer_type(answers)
    reference_sets = _qasper_reference_sets(
        document_id,
        answer_annotations,
        evidence,
    )
    return {
        "example_id": str(qa.get("question_id") or f"{document_id}_{index}"),
        "document_ids": [document_id],
        "scope": "document",
        "modality": "text",
        "answer_type": answer_type,
        "question": str(qa.get("question") or "").strip(),
        "answers": answers,
        "evidence_sources": [
            f"{document_id}#evidence:{evidence_index + 1}"
            for evidence_index, _item in enumerate(evidence)
        ],
        "gold_source_ids": [document_id],
        "gold_evidence_texts": evidence,
        "gold_evidence": [
            {
                "document_id": document_id,
                "span": item,
                "citation": f"{document_id}#evidence:{evidence_index + 1}",
            }
            for evidence_index, item in enumerate(evidence)
        ],
        "metadata": {
            "dataset_family": "scientific_qa",
            "nlp_background": qa.get("nlp_background"),
            "topic_background": qa.get("topic_background"),
            "qasper_answer_type": answer_type,
            "qasper_answer_annotations": answer_annotations,
            "qasper_reference_set_contract": "qasper_reference_sets.v1",
            "qasper_reference_sets": reference_sets,
        },
    }


def _qasper_answer_type(answers: list[str]) -> str:
    normalized = {str(answer or "").strip().lower() for answer in answers}
    if normalized == {"unanswerable"}:
        return "unanswerable"
    if normalized and normalized <= {"yes", "no"}:
        return "boolean"
    return "free_text"


def _answers_evidence_and_annotations(
    qa: dict[str, Any],
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    answers: list[str] = []
    evidence: list[str] = []
    answer_annotations: list[dict[str, Any]] = []
    for annotation in ensure_list(qa.get("answers")):
        if not isinstance(annotation, dict):
            continue
        answer = annotation.get("answer")
        if not isinstance(answer, dict):
            continue
        answers.extend(_answer_texts(answer))
        answer_annotations.append(_answer_annotation(annotation))
        for item in ensure_list(answer.get("evidence")):
            text = str(item).strip()
            if text:
                evidence.append(text)
    return _dedupe(answers), _dedupe(evidence), answer_annotations


def _answer_annotation(annotation: dict[str, Any]) -> dict[str, Any]:
    answer = annotation.get("answer")
    answer = answer if isinstance(answer, dict) else {}
    payload = {
        "extractive_spans": [
            str(item).strip()
            for item in ensure_list(answer.get("extractive_spans"))
            if str(item).strip()
        ],
        "free_form_answer": str(answer.get("free_form_answer") or "").strip(),
        "yes_no": answer.get("yes_no"),
        "unanswerable": answer.get("unanswerable"),
        "evidence": [
            str(item).strip()
            for item in ensure_list(answer.get("evidence"))
            if str(item).strip()
        ],
    }
    annotation_id = str(annotation.get("annotation_id") or "").strip()
    worker_id = str(annotation.get("worker_id") or "").strip()
    if annotation_id:
        payload["annotation_id"] = annotation_id
    if worker_id:
        payload["worker_id"] = worker_id
    if "highlighted_evidence" in answer:
        payload["highlighted_evidence"] = [
            str(item).strip()
            for item in ensure_list(answer.get("highlighted_evidence"))
            if str(item).strip()
        ]
    return payload


def _qasper_reference_sets(
    document_id: str,
    annotations: list[dict[str, Any]],
    union_evidence: list[str],
) -> list[dict[str, Any]]:
    evidence_sources = {
        text: f"{document_id}#evidence:{index + 1}"
        for index, text in enumerate(union_evidence)
    }
    output: list[dict[str, Any]] = []
    for index, annotation in enumerate(annotations):
        answers = _answer_texts(annotation)
        evidence = [str(value) for value in annotation.get("evidence") or []]
        highlighted = [
            str(value) for value in annotation.get("highlighted_evidence") or []
        ]
        annotation_id = str(annotation.get("annotation_id") or "").strip()
        output.append(
            {
                "reference_id": annotation_id or f"reference:{index + 1}",
                "annotation_id": annotation_id,
                "worker_id": str(annotation.get("worker_id") or "").strip(),
                "answer_type": _qasper_answer_type(answers),
                "answers": answers,
                "gold_support_mode": _gold_support_mode(answers, evidence),
                "evidence_texts": evidence,
                "highlighted_evidence_texts": highlighted,
                "evidence_source_ids": [
                    evidence_sources[value]
                    for value in evidence
                    if value in evidence_sources
                ],
            }
        )
    return output


def _gold_support_mode(answers: list[str], evidence: list[str]) -> str:
    if any(value.startswith("FLOAT SELECTED:") for value in evidence):
        return "multimodal"
    if not evidence and _qasper_answer_type(answers) == "boolean" and answers == ["no"]:
        return "absence_bounded"
    if len(evidence) > 1:
        return "paragraph_set"
    return "single_span"


def _answer_texts(answer: dict[str, Any]) -> list[str]:
    if answer.get("unanswerable"):
        return ["unanswerable"]
    yes_no = answer.get("yes_no")
    if yes_no is not None:
        return ["yes" if bool(yes_no) else "no"]
    values = [
        str(item).strip()
        for item in ensure_list(answer.get("extractive_spans"))
        if str(item).strip()
    ]
    free_form = str(answer.get("free_form_answer") or "").strip()
    if free_form:
        values.append(free_form)
    return values


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            output.append(item)
    return output
