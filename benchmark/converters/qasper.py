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
    return "\n\n".join(part for part in parts if part)


def _example(document_id: str, qa: dict[str, Any], index: int) -> dict[str, Any]:
    answers, evidence = _answers_and_evidence(qa)
    return {
        "example_id": str(qa.get("question_id") or f"{document_id}_{index}"),
        "document_ids": [document_id],
        "scope": "document",
        "modality": "text",
        "answer_type": "evidence_qa",
        "question": str(qa.get("question") or "").strip(),
        "answers": answers,
        "evidence_sources": evidence,
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
        },
    }


def _answers_and_evidence(qa: dict[str, Any]) -> tuple[list[str], list[str]]:
    answers: list[str] = []
    evidence: list[str] = []
    for annotation in ensure_list(qa.get("answers")):
        if not isinstance(annotation, dict):
            continue
        answer = annotation.get("answer")
        if not isinstance(answer, dict):
            continue
        answers.extend(_answer_texts(answer))
        for item in ensure_list(answer.get("evidence")):
            text = str(item).strip()
            if text:
                evidence.append(text)
    return _dedupe(answers), _dedupe(evidence)


def _answer_texts(answer: dict[str, Any]) -> list[str]:
    if answer.get("unanswerable"):
        return ["unanswerable"]
    yes_no = answer.get("yes_no")
    if yes_no is not None:
        return [str(yes_no).lower()]
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
