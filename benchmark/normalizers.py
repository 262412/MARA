from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .manifest import write_manifest


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _pick(record: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return default


def _ensure_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _find_document(prefix: str, directory: Path, suffixes: set[str]) -> Path | None:
    for candidate in sorted(directory.glob(f"{prefix}_*")):
        if candidate.suffix.lower() in suffixes:
            return candidate
    return None


def normalize_format_robustness_manifest(
    source_dir: str | Path,
    output_path: str | Path,
) -> Path:
    source_dir = Path(source_dir).resolve()
    allowed_suffixes = {".pdf", ".doc", ".docx", ".ppt", ".pptx", ".txt"}
    records: list[dict[str, Any]] = []

    for format_dir in sorted(path for path in source_dir.iterdir() if path.is_dir()):
        for metadata_path in sorted(format_dir.glob("*_metadata.json")):
            metadata = _load_json(metadata_path)
            prefix = metadata_path.stem.split("_", 1)[0]
            document_path = _find_document(prefix, format_dir, allowed_suffixes)
            if document_path is None:
                continue

            document_id = f"{format_dir.name}_{prefix}"
            for question_index, qa in enumerate(metadata.get("questions", [])):
                question = str(_pick(qa, "question", default="")).strip()
                answer = str(_pick(qa, "answer", default="")).strip()
                if not question:
                    continue
                records.append(
                    {
                        "dataset_name": "format_robustness",
                        "example_id": f"{document_id}_{question_index}",
                        "document_id": document_id,
                        "document_path": str(document_path),
                        "format_type": format_dir.name.lower(),
                        "question": question,
                        "answers": [answer] if answer else [],
                        "metadata": {
                            "source_metadata_file": str(metadata_path),
                            "file_name": metadata.get("file_name", ""),
                        },
                    }
                )

    return write_manifest(output_path, "format_robustness", records)


def normalize_financebench_manifest(
    source_dir: str | Path,
    output_path: str | Path,
    pdf_root: str | Path | None = None,
) -> Path:
    source_dir = Path(source_dir).resolve()
    pdf_root = Path(pdf_root).resolve() if pdf_root else (source_dir / "pdfs").resolve()
    data_path = source_dir / "data" / "financebench_open_source.jsonl"
    records: list[dict[str, Any]] = []

    for index, record in enumerate(_load_jsonl(data_path)):
        document_name = str(
            _pick(record, "doc_name", "document_name", "document", default="")
        ).strip()
        if not document_name:
            raise ValueError("FinanceBench record is missing `doc_name`.")

        document_path = pdf_root / document_name
        if not document_path.suffix:
            document_path = document_path.with_suffix(".pdf")

        answers = [
            str(item).strip()
            for item in _ensure_list(_pick(record, "answers", "answer", default=[]))
            if str(item).strip()
        ]
        evidence = [
            str(item).strip()
            for item in _ensure_list(
                _pick(
                    record,
                    "evidence",
                    "evidence_text",
                    "evidence_strings",
                    default=[],
                )
            )
            if str(item).strip()
        ]

        records.append(
            {
                "dataset_name": "financebench",
                "example_id": str(_pick(record, "id", "question_id", default=index)),
                "document_id": document_path.stem,
                "document_path": str(document_path),
                "format_type": "pdf",
                "question": str(_pick(record, "question", default="")).strip(),
                "answers": answers,
                "evidence_sources": evidence,
                "metadata": {
                    "doc_name": document_name,
                },
            }
        )

    return write_manifest(output_path, "financebench", records)


def normalize_slidevqa_manifest(
    annotations_path: str | Path,
    documents_root: str | Path,
    output_path: str | Path,
) -> Path:
    annotations_path = Path(annotations_path).resolve()
    documents_root = Path(documents_root).resolve()
    annotations = _load_json(annotations_path)
    if isinstance(annotations, dict):
        annotations = annotations.get("data", [])
    if not isinstance(annotations, list):
        raise ValueError(
            "SlideVQA annotations must be a JSON list or {data: [...]} object."
        )

    path_index: dict[str, Path] = {}
    for candidate in documents_root.rglob("*"):
        if candidate.is_file() and candidate.suffix.lower() in {
            ".pdf",
            ".ppt",
            ".pptx",
            ".txt",
            ".json",
        }:
            path_index[candidate.stem.lower()] = candidate

    records: list[dict[str, Any]] = []
    for index, record in enumerate(annotations):
        deck_name = str(_pick(record, "deck_name", "document_name", default="")).strip()
        if not deck_name:
            continue

        document_path = path_index.get(Path(deck_name).stem.lower())
        if document_path is None:
            continue

        answer = str(_pick(record, "answer", default="")).strip()
        records.append(
            {
                "dataset_name": "slidevqa",
                "example_id": str(_pick(record, "qa_id", default=index)),
                "document_id": document_path.stem,
                "document_path": str(document_path),
                "format_type": document_path.suffix.lower().lstrip("."),
                "question": str(_pick(record, "question", default="")).strip(),
                "answers": [answer] if answer else [],
                "evidence_pages": _ensure_list(record.get("evidence_pages")),
                "metadata": {
                    "deck_name": deck_name,
                    "reasoning_type": record.get("reasoning_type"),
                    "answer_type": record.get("answer_type"),
                },
            }
        )

    return write_manifest(output_path, "slidevqa", records)
