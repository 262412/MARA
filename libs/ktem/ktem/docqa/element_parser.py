from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from .financial_statement_identity import financial_statement_identity

SUPPORTED_ELEMENT_MODALITIES = {"table", "figure", "formula", "slide"}
LOCAL_ELEMENT_PARSER = "local_element_parser_v1"
ELEMENT_SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class ElementIndexRecord:
    evidence_id: str
    file_id: str
    file_name: str
    page_label: str
    element_id: str
    modality: str
    bbox: Any = None
    caption: str = ""
    text: str = ""
    source_backrefs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "file_id": self.file_id,
            "file_name": self.file_name,
            "page_label": self.page_label,
            "element_id": self.element_id,
            "modality": self.modality,
            "bbox": self.bbox,
            "caption": self.caption,
            "text": self.text,
            "source_backrefs": list(self.source_backrefs),
            "metadata": dict(self.metadata),
        }


def parse_element_index_record(
    *,
    doc_id: str,
    file_id: str,
    file_name: str,
    page_label: str,
    text: str,
    metadata: dict[str, Any],
) -> dict[str, Any] | None:
    records = parse_element_index_records(
        doc_id=doc_id,
        file_id=file_id,
        file_name=file_name,
        page_label=page_label,
        text=text,
        metadata=metadata,
    )
    return records[0] if records else None


def parse_element_index_records(
    *,
    doc_id: str,
    file_id: str,
    file_name: str,
    page_label: str,
    text: str,
    metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    declared = str(
        metadata.get("modality") or metadata.get("element_type") or ""
    ).strip()
    if declared in SUPPORTED_ELEMENT_MODALITIES:
        return [
            _element_record(
                doc_id=doc_id,
                file_id=file_id,
                file_name=file_name,
                page_label=page_label,
                text=text,
                metadata=metadata,
                modality=declared,
            )
        ]

    modality = _element_modality(metadata, text)
    if not modality:
        return []
    if modality == "table":
        blocks = _financial_table_blocks(text)
        if blocks:
            page_statement_kind, page_scope = financial_statement_identity(text)
            return [
                _element_record(
                    doc_id=(doc_id if len(blocks) == 1 else f"{doc_id}-block-{index}"),
                    parser_source_doc_id=doc_id,
                    file_id=file_id,
                    file_name=file_name,
                    page_label=page_label,
                    text=block,
                    metadata=metadata,
                    modality=modality,
                    financial_identity=True,
                    fallback_statement_kind=page_statement_kind,
                    fallback_financial_scope=page_scope,
                )
                for index, block in enumerate(blocks, start=1)
            ]
    return [
        _element_record(
            doc_id=doc_id,
            file_id=file_id,
            file_name=file_name,
            page_label=page_label,
            text=text,
            metadata=metadata,
            modality=modality,
        )
    ]


def _element_record(
    *,
    doc_id: str,
    file_id: str,
    file_name: str,
    page_label: str,
    text: str,
    metadata: dict[str, Any],
    modality: str,
    financial_identity: bool = False,
    fallback_statement_kind: str = "",
    fallback_financial_scope: str = "",
    parser_source_doc_id: str = "",
) -> dict[str, Any]:
    parser_metadata = _parser_metadata(parser_source_doc_id or doc_id)
    if financial_identity:
        statement_kind, financial_scope = financial_statement_identity(text)
        parser_metadata.update(
            {
                "statement_kind": statement_kind or fallback_statement_kind,
                "financial_scope": financial_scope or fallback_financial_scope,
            }
        )

    element_id = _element_id(modality, doc_id, text)
    record = ElementIndexRecord(
        evidence_id=f"element:{file_id}:{page_label}:{element_id}",
        file_id=file_id,
        file_name=file_name,
        page_label=page_label,
        element_id=element_id,
        modality=modality,
        bbox=metadata.get("bbox"),
        caption=str(metadata.get("caption") or _caption_from_text(text, modality)),
        text=text,
        source_backrefs=[f"{file_id}#page:{page_label}"],
        metadata=parser_metadata,
    )
    return record.as_dict()


def _element_modality(metadata: dict[str, Any], text: str) -> str:
    declared = str(
        metadata.get("modality") or metadata.get("element_type") or ""
    ).strip()
    if declared in SUPPORTED_ELEMENT_MODALITIES:
        return declared
    return _infer_modality(text)


def _infer_modality(text: str) -> str:
    lowered = str(text or "").strip().lower()
    if lowered.startswith("formula:"):
        return "formula"
    if lowered.startswith("table:") or _looks_like_markdown_table(text):
        return "table"
    if lowered.startswith(("figure:", "chart:")):
        return "figure"
    if lowered.startswith("slide:"):
        return "slide"
    if _looks_like_financial_table(text):
        return "table"
    return ""


def _looks_like_markdown_table(text: str) -> bool:
    lines = [line for line in str(text or "").splitlines() if line.strip()]
    return len([line for line in lines if "|" in line]) >= 2


def _looks_like_financial_table(text: str) -> bool:
    value = str(text or "")
    if not re.search(
        r"(?:selected financial data|balance sheets?|"
        r"statements? of (?:income|operations|cash flows?|financial position)|"
        r"\(\s*in\s+(?:thousands?|millions?|billions?)\b)",
        value,
        flags=re.IGNORECASE,
    ):
        return False
    numeric_rows = 0
    for line in value.splitlines():
        numbers = re.findall(r"\(?\$?\s*\d[\d,]*(?:\.\d+)?\)?", line)
        if len(numbers) >= 2:
            numeric_rows += 1
    return numeric_rows >= 2


def _financial_table_blocks(text: str) -> tuple[str, ...]:
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    headers = [
        index
        for index, line in enumerate(lines)
        if len(set(re.findall(r"\b(?:19|20)\d{2}\b", line))) >= 2
    ]
    if not headers:
        return ()
    blocks: list[str] = []
    for header_index in headers:
        start = max(0, header_index - 1)
        block_lines = lines[start : header_index + 1]
        numeric_rows = 0
        for line in lines[header_index + 1 :]:
            if len(set(re.findall(r"\b(?:19|20)\d{2}\b", line))) >= 2:
                break
            numbers = re.findall(r"\(?\$?\s*\d[\d,]*(?:\.\d+)?\)?", line)
            if len(numbers) >= 2:
                block_lines.append(line)
                numeric_rows += 1
                continue
            if numeric_rows >= 2:
                break
            block_lines.append(line)
        if numeric_rows >= 2:
            blocks.append("\n".join(block_lines))
    return tuple(blocks)


def _caption_from_text(text: str, modality: str) -> str:
    prefix = f"{modality}:"
    first_line = str(text or "").strip().splitlines()[0:1]
    if not first_line:
        return ""
    line = first_line[0].strip()
    if line.lower().startswith(prefix):
        return line[len(prefix) :].strip()
    return ""


def _element_id(modality: str, doc_id: str, text: str) -> str:
    suffix = _slug(doc_id) or hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    return f"{modality}-{suffix}"


def _slug(value: str) -> str:
    return "-".join(
        token
        for token in re.findall(r"[a-zA-Z0-9]+", str(value or "").lower())
        if token
    )


def _parser_metadata(doc_id: str) -> dict[str, Any]:
    metadata = {
        "element_schema_version": ELEMENT_SCHEMA_VERSION,
        "index_source": "docstore_document",
        "parser_backend": LOCAL_ELEMENT_PARSER,
    }
    if doc_id:
        metadata["parser_source_doc_id"] = doc_id
    return metadata
