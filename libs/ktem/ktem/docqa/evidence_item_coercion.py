from __future__ import annotations

from typing import Any

from .evidence_field_values import (
    atomic_identity_fields,
    item_metadata_text,
    retrieval_lineage_values,
    visual_evidence_fields,
)
from .evidence_locators import source_alias_values
from .evidence_schema import EvidenceElement


def coerce_item(item: dict[str, Any]) -> dict[str, Any]:
    metadata = _merged_item_metadata(item)
    file_id, page_label, modality, backrefs = _coerced_locator_fields(
        item,
        metadata,
    )
    return EvidenceElement(
        evidence_id=str(item.get("evidence_id") or item.get("doc_id") or "").strip(),
        **_source_projection(
            item,
            metadata,
            file_id=file_id,
            page_label=page_label,
            modality=modality,
            backrefs=backrefs,
        ),
        element_id=str(item.get("element_id") or "").strip(),
        **visual_evidence_fields(item, metadata),
        **atomic_identity_fields(item, metadata),
        canonical_id=str(item.get("canonical_id") or "").strip(),
        parent_element_id=str(
            item.get("parent_element_id") or metadata.get("parent_element_id") or ""
        ).strip(),
        neighbor_element_ids=_string_values(
            item.get("neighbor_element_ids")
            or metadata.get("neighbor_element_ids")
            or metadata.get("neighbors")
        ),
        section_id=str(
            item.get("section_id") or metadata.get("section_id") or ""
        ).strip(),
        table_id=str(item.get("table_id") or metadata.get("table_id") or "").strip(),
        table_instance_id=item_metadata_text(
            item,
            metadata,
            "table_instance_id",
        ),
        table_group_id=item_metadata_text(item, metadata, "table_group_id"),
        block_id=item_metadata_text(item, metadata, "block_id"),
        cell_role=item_metadata_text(item, metadata, "cell_role"),
        materialization_source_id=item_metadata_text(
            item,
            metadata,
            "materialization_source_id",
        ),
        row_index=_optional_int(item.get("row_index", metadata.get("row_index"))),
        column_index=_optional_int(
            item.get("column_index", metadata.get("column_index"))
        ),
        row_label=str(item.get("row_label") or metadata.get("row_label") or "").strip(),
        column_label=str(
            item.get("column_label") or metadata.get("column_label") or ""
        ).strip(),
        period=str(item.get("period") or metadata.get("period") or "").strip(),
        period_kind=item_metadata_text(item, metadata, "period_kind"),
        value=item_metadata_text(item, metadata, "value"),
        unit=str(item.get("unit") or metadata.get("unit") or "").strip(),
        scale=str(item.get("scale") or metadata.get("scale") or "").strip(),
        currency=str(item.get("currency") or metadata.get("currency") or "").strip(),
        statement_kind=item_metadata_text(item, metadata, "statement_kind"),
        financial_scope=item_metadata_text(item, metadata, "financial_scope"),
        continuation_id=str(
            item.get("continuation_id")
            or metadata.get("continuation_id")
            or metadata.get("table_continuation_id")
            or ""
        ).strip(),
        chunk_start=_optional_int(item.get("chunk_start", metadata.get("chunk_start"))),
        chunk_end=_optional_int(item.get("chunk_end", metadata.get("chunk_end"))),
        normalized_text_hash=str(item.get("normalized_text_hash") or "").strip(),
        duplicate_evidence_ids=_string_values(item.get("duplicate_evidence_ids")),
        retrieval_lineage=retrieval_lineage_values(item, metadata),
        text=str(item.get("text") or item.get("content") or "").strip(),
        evidence_level=str(item.get("evidence_level") or "page").strip(),
        metadata=metadata,
    ).as_dict()


def _source_projection(
    item: dict[str, Any],
    metadata: dict[str, Any],
    *,
    file_id: str,
    page_label: str,
    modality: str,
    backrefs: list[str],
) -> dict[str, Any]:
    return {
        "source_id": file_id,
        "runtime_source_id": item_metadata_text(
            item,
            metadata,
            "runtime_source_id",
        ),
        "evaluation_source_id": item_metadata_text(
            item,
            metadata,
            "evaluation_source_id",
        ),
        "runtime_identity": item_metadata_text(item, metadata, "runtime_identity"),
        "evaluation_identity": item_metadata_text(
            item,
            metadata,
            "evaluation_identity",
        ),
        "source_name": str(
            item.get("file_name")
            or item.get("source_name")
            or metadata.get("file_name")
            or metadata.get("source_name")
            or ""
        ).strip(),
        "source_aliases": source_alias_values(item, metadata, file_id),
        "page_label": page_label,
        "dataset_page": str(
            item.get("dataset_page") or metadata.get("dataset_page") or ""
        ).strip(),
        "parser_page_index": _optional_int(
            item.get("parser_page_index", metadata.get("parser_page_index"))
        ),
        "page_aliases": _string_values(
            item.get("page_aliases") or metadata.get("page_aliases")
        ),
        "modality": modality or "text",
        "source_backrefs": backrefs,
        "runtime_source_backrefs": _string_values(
            item.get("runtime_source_backrefs")
            or metadata.get("runtime_source_backrefs")
        ),
        "evaluation_source_backrefs": _string_values(
            item.get("evaluation_source_backrefs")
            or metadata.get("evaluation_source_backrefs")
        ),
    }


def _coerced_locator_fields(
    item: dict[str, Any],
    metadata: dict[str, Any],
) -> tuple[str, str, str, list[str]]:
    file_id = str(
        item.get("file_id")
        or item.get("source_id")
        or item.get("runtime_source_id")
        or metadata.get("file_id")
        or metadata.get("source_id")
        or metadata.get("runtime_source_id")
        or ""
    ).strip()
    page_label = str(
        item.get("page_label")
        or item.get("page")
        or metadata.get("page_label")
        or metadata.get("page_number")
        or metadata.get("page")
        or ""
    ).strip()
    modality = str(
        item.get("modality")
        or item.get("element_type")
        or item.get("type")
        or metadata.get("element_type")
        or metadata.get("type")
        or "text"
    ).strip()
    backrefs = _source_backrefs_from_item(item, metadata)
    if not backrefs and file_id and page_label:
        backrefs = [f"{file_id}#page:{page_label}"]
    return file_id, page_label, modality, backrefs


def _merged_item_metadata(item: dict[str, Any]) -> dict[str, Any]:
    metadata = dict(item.get("metadata") or {})
    nested = metadata.get("metadata")
    if isinstance(nested, dict):
        merged = dict(nested)
        merged.update(metadata)
        return merged
    return metadata


def _source_backrefs_from_item(
    item: dict[str, Any],
    metadata: dict[str, Any],
) -> list[str]:
    source = item.get("source_backrefs") or metadata.get("source_backrefs") or []
    if isinstance(source, str):
        return [source] if source else []
    return list(source)


def _string_values(value: Any) -> list[str]:
    if isinstance(value, dict):
        values: list[Any] = list(value.values())
    elif isinstance(value, (list, tuple, set)):
        values = list(value)
    elif value is None:
        return []
    else:
        values = [value]
    return list(
        dict.fromkeys(str(item).strip() for item in values if str(item).strip())
    )


def _optional_int(value: Any) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
