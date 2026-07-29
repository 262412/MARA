from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from .finance_query_planning import FINANCE_METRIC_ALIASES
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
    evidence_level: str = "element"
    table_id: str = ""
    table_instance_id: str = ""
    table_group_id: str = ""
    block_id: str = ""
    cell_id: str = ""
    cell_role: str = ""
    physical_cell_identity: dict[str, Any] | None = None
    semantic_cell_key: dict[str, str] | None = None
    parent_element_id: str = ""
    row_index: int | None = None
    column_index: int | None = None
    row_label: str = ""
    column_label: str = ""
    period: str = ""
    period_kind: str = ""
    value: str = ""
    unit: str = ""
    scale: str = ""
    currency: str = ""
    statement_kind: str = ""
    financial_scope: str = ""
    bbox: Any = None
    caption: str = ""
    text: str = ""
    source_backrefs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = {
            "evidence_id": self.evidence_id,
            "file_id": self.file_id,
            "file_name": self.file_name,
            "page_label": self.page_label,
            "element_id": self.element_id,
            "modality": self.modality,
            "evidence_level": self.evidence_level,
            "table_id": self.table_id,
            "table_instance_id": self.table_instance_id,
            "table_group_id": self.table_group_id,
            "block_id": self.block_id,
            "cell_id": self.cell_id,
            "cell_role": self.cell_role,
            "physical_cell_identity": self.physical_cell_identity,
            "semantic_cell_key": self.semantic_cell_key,
            "parent_element_id": self.parent_element_id,
            "row_index": self.row_index,
            "column_index": self.column_index,
            "row_label": self.row_label,
            "column_label": self.column_label,
            "period": self.period,
            "period_kind": self.period_kind,
            "value": self.value,
            "unit": self.unit,
            "scale": self.scale,
            "currency": self.currency,
            "statement_kind": self.statement_kind,
            "financial_scope": self.financial_scope,
            "bbox": self.bbox,
            "caption": self.caption,
            "text": self.text,
            "source_backrefs": list(self.source_backrefs),
            "metadata": dict(self.metadata),
        }
        for key in (
            "cell_id",
            "cell_role",
            "physical_cell_identity",
            "semantic_cell_key",
            "table_instance_id",
            "table_group_id",
            "block_id",
            "parent_element_id",
            "row_index",
            "column_index",
            "row_label",
            "column_label",
            "period",
            "period_kind",
            "value",
            "unit",
            "scale",
            "currency",
            "statement_kind",
            "financial_scope",
        ):
            if payload[key] in (None, "", []):
                payload.pop(key)
        return payload


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
        return _with_financial_cells(
            _element_record(
                doc_id=doc_id,
                file_id=file_id,
                file_name=file_name,
                page_label=page_label,
                text=text,
                metadata=metadata,
                modality=declared,
            )
        )

    modality = _element_modality(metadata, text)
    if not modality:
        return []
    if modality == "table":
        blocks = _financial_table_blocks(text)
        if blocks:
            page_statement_kind, page_scope = financial_statement_identity(text)
            records = [
                _element_record(
                    doc_id=(doc_id if len(blocks) == 1 else f"{doc_id}-block-{index}"),
                    parser_source_doc_id=doc_id,
                    parser_block_id=f"block-{index}",
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
                record
                for table_record in records
                for record in _with_financial_cells(table_record)
            ]
    return _with_financial_cells(
        _element_record(
            doc_id=doc_id,
            file_id=file_id,
            file_name=file_name,
            page_label=page_label,
            text=text,
            metadata=metadata,
            modality=modality,
        )
    )


def parse_financial_numeric_span_records(
    *,
    doc_id: str,
    file_id: str,
    file_name: str,
    page_label: str,
    text: str,
    metadata: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract atomic, finance-specific amount spans from narrative text."""
    modality = str(
        metadata.get("modality") or metadata.get("element_type") or ""
    ).strip()
    if modality in SUPPORTED_ELEMENT_MODALITIES:
        return []

    parent_element_id = str(metadata.get("element_id") or "").strip()
    records: list[dict[str, Any]] = []
    for span_index, clause in enumerate(_financial_fact_clauses(text), start=1):
        metric = _finance_metric(clause)
        amounts = _financial_amounts(clause)
        if not metric or len(amounts) != 1:
            continue
        value, scale, currency = amounts[0]
        period_match = re.search(r"\b(?:19|20)\d{2}\b", clause)
        period = period_match.group(0) if period_match else ""
        digest = hashlib.sha256(
            f"{doc_id}:{span_index}:{clause}".encode("utf-8")
        ).hexdigest()[:16]
        element_id = f"span-{digest}"
        parser_metadata = _parser_metadata(doc_id)
        parser_metadata["parser_record_type"] = "financial_numeric_span"
        records.append(
            ElementIndexRecord(
                evidence_id=f"span:{file_id}:{page_label}:{element_id}",
                file_id=file_id,
                file_name=file_name,
                page_label=page_label,
                element_id=element_id,
                modality="text",
                evidence_level="span",
                parent_element_id=parent_element_id,
                row_label=metric,
                column_label=period,
                period=period,
                value=str(value),
                scale=scale,
                currency=currency,
                caption=metric,
                text=clause,
                source_backrefs=[f"{file_id}#page:{page_label}"],
                metadata=parser_metadata,
            ).as_dict()
        )
    return records


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
    parser_block_id: str = "",
) -> dict[str, Any]:
    element_metadata = metadata.get("element_metadata")
    parser_metadata = (
        dict(element_metadata) if isinstance(element_metadata, dict) else {}
    )
    parser_metadata.update(_parser_metadata(parser_source_doc_id or doc_id))
    if financial_identity or modality == "table":
        statement_kind, financial_scope = financial_statement_identity(text)
        resolved_kind = statement_kind or fallback_statement_kind
        resolved_scope = financial_scope or fallback_financial_scope
        if resolved_kind:
            parser_metadata["statement_kind"] = resolved_kind
        if resolved_scope:
            parser_metadata["financial_scope"] = resolved_scope

    explicit_element_id = str(metadata.get("element_id") or "").strip()
    element_id = (
        explicit_element_id
        if explicit_element_id and not parser_source_doc_id
        else _element_id(modality, doc_id, text)
    )
    table_instance_id = str(
        metadata.get("table_instance_id") or element_id if modality == "table" else ""
    ).strip()
    table_group_id = str(
        metadata.get("table_group_id")
        or metadata.get("continuation_id")
        or (parser_source_doc_id if modality == "table" else "")
        or table_instance_id
    ).strip()
    block_id = str(
        metadata.get("block_id")
        or parser_block_id
        or (doc_id if modality == "table" else "")
    ).strip()
    record = ElementIndexRecord(
        evidence_id=f"element:{file_id}:{page_label}:{element_id}",
        file_id=file_id,
        file_name=file_name,
        page_label=page_label,
        element_id=element_id,
        modality=modality,
        evidence_level="element",
        table_id=element_id if modality == "table" else "",
        table_instance_id=table_instance_id,
        table_group_id=table_group_id,
        block_id=block_id,
        period_kind=_period_kind(text),
        statement_kind=str(parser_metadata.get("statement_kind") or ""),
        financial_scope=str(parser_metadata.get("financial_scope") or ""),
        bbox=metadata.get("bbox"),
        caption=str(metadata.get("caption") or _caption_from_text(text, modality)),
        text=text,
        source_backrefs=[f"{file_id}#page:{page_label}"],
        metadata=parser_metadata,
    )
    return record.as_dict()


def _with_financial_cells(record: dict[str, Any]) -> list[dict[str, Any]]:
    if str(record.get("modality") or "") != "table":
        return [record]
    from .financial_table import parse_financial_table_cells

    cells = parse_financial_table_cells(record)
    if not cells:
        return [record]
    metadata = dict(record.get("metadata") or {})
    cell_records = []
    for cell in cells:
        cell_records.append(
            ElementIndexRecord(
                evidence_id=cell.cell_id,
                file_id=str(record.get("file_id") or ""),
                file_name=str(record.get("file_name") or ""),
                page_label=cell.page_label,
                element_id=cell.table_id,
                modality="table",
                evidence_level="cell",
                table_id=cell.table_id,
                table_instance_id=cell.table_instance_id,
                table_group_id=cell.table_group_id,
                block_id=cell.block_id,
                cell_id=cell.cell_id,
                cell_role=cell.cell_role,
                physical_cell_identity=cell.physical_identity.as_dict(),
                semantic_cell_key=cell.semantic_key.as_dict(),
                parent_element_id=cell.table_id,
                row_index=cell.row_index,
                column_index=cell.column_index,
                row_label=cell.row_label,
                column_label=cell.column_label,
                period=cell.period,
                period_kind=cell.period_kind,
                value=str(cell.value),
                unit=cell.unit,
                scale=cell.scale,
                currency=cell.currency,
                statement_kind=cell.statement_kind,
                financial_scope=cell.financial_scope,
                bbox=record.get("bbox"),
                caption=cell.row_label,
                text=cell.verification_text(),
                source_backrefs=list(record.get("source_backrefs") or []),
                metadata=metadata,
            ).as_dict()
        )
    return [record, *cell_records]


def _period_kind(text: str) -> str:
    lowered = str(text or "").lower()
    if "three months ended" in lowered or "quarter" in lowered:
        return "quarter"
    if "twelve months ended" in lowered or "fiscal year" in lowered:
        return "fiscal_year"
    return ""


def _financial_fact_clauses(text: str) -> tuple[str, ...]:
    return tuple(
        " ".join(clause.split())
        for paragraph in re.split(r"(?:\r?\n){2,}", str(text or ""))
        for clause in re.split(
            r"(?<=[.!?])\s+(?=[A-Z])|[;]+",
            " ".join(line.strip() for line in paragraph.splitlines()),
        )
        if clause.strip()
    )


def _finance_metric(text: str) -> str:
    normalized = _normalized_words(text)
    if "credit agreement" in normalized and "borrow up to" in normalized:
        return "revolving credit capacity"
    for metric, aliases in FINANCE_METRIC_ALIASES.items():
        if any(
            f" {_normalized_words(alias)} " in f" {normalized} " for alias in aliases
        ):
            return metric
    return ""


def _financial_amounts(text: str) -> tuple[tuple[Decimal, str, str], ...]:
    pattern = re.compile(
        r"(?:(?P<currency>[$€£¥])\s*)?"
        r"(?P<value>\(?[+-]?\d[\d,]*(?:\.\d+)?\)?)"
        r"(?:\s*(?P<scale>thousands?|millions?|billions?))?",
        flags=re.IGNORECASE,
    )
    values: list[tuple[Decimal, str, str]] = []
    for match in pattern.finditer(text):
        currency_symbol = str(match.group("currency") or "")
        scale = str(match.group("scale") or "").lower().rstrip("s")
        if not currency_symbol and not scale:
            continue
        value = _decimal_amount(match.group("value"))
        if value is None:
            continue
        currency = {
            "$": "USD",
            "€": "EUR",
            "£": "GBP",
            "¥": "JPY",
        }.get(currency_symbol, "")
        values.append((value, scale, currency))
    return tuple(values)


def _decimal_amount(value: str) -> Decimal | None:
    normalized = str(value or "").replace(",", "").strip()
    negative = normalized.startswith("(") and normalized.endswith(")")
    try:
        parsed = Decimal(normalized.strip("()"))
    except InvalidOperation:
        return None
    return -parsed if negative else parsed


def _normalized_words(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))


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
