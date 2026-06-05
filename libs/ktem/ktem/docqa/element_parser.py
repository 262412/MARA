from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

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
    modality = _element_modality(metadata, text)
    if not modality:
        return None

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
        metadata=_parser_metadata(doc_id),
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
    return ""


def _looks_like_markdown_table(text: str) -> bool:
    lines = [line for line in str(text or "").splitlines() if line.strip()]
    return len([line for line in lines if "|" in line]) >= 2


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
