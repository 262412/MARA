from __future__ import annotations

from typing import Any

from .element_record_contract import element_record_from_mapping
from .evidence_identity import identity_of
from .source_identity_crosswalk import SourceIdentityResolver

VISUAL_EVIDENCE_AUTHORITY_CONTRACT = "visual_evidence_authority.v1"
TYPED_VISUAL_EVIDENCE_PATH_CONTRACT = "typed_visual_evidence_path.v1"
_VISUAL_EXTRACTION_KEYS = (
    "visual_extractions",
    "structured_visual_evidence",
    "table_cells",
    "ocr_cells",
    "vlm_cells",
    "extracted_elements",
    "visual_elements",
    "ocr_table",
    "vlm_table",
)
_NON_ANSWER_MARKERS = (
    "could not retrieve enough evidence",
    "no vlm backend is configured",
    "unable to answer from the visual evidence",
)


def record_visual_answer_authority(
    bundle: Any,
    answer: str,
    *,
    backend: str,
) -> bool:
    """Bind a visual answer to the page identities supplied to the generator."""

    value = str(answer or "").strip()
    if not value or any(marker in value.lower() for marker in _NON_ANSWER_MARKERS):
        return False
    evidence_ids = _page_evidence_ids(bundle)
    if not evidence_ids:
        return False
    metadata = getattr(bundle, "metadata", None)
    if not isinstance(metadata, dict):
        return False
    authority: dict[str, Any] = {
        "contract_id": VISUAL_EVIDENCE_AUTHORITY_CONTRACT,
        "answer": value,
        "evidence_ids": evidence_ids,
        "backend": str(backend or "visual_generator"),
    }
    typed_path = typed_visual_evidence_path(bundle)
    if typed_path is not None:
        authority["typed_visual_path"] = typed_path
    metadata["visual_answer_authority"] = authority
    return True


def validated_visual_answer_authority(
    bundle: Any,
    answer: str,
) -> dict[str, Any] | None:
    """Return a visual authority only when it still matches selected page evidence."""

    metadata = getattr(bundle, "metadata", None)
    authority = (
        metadata.get("visual_answer_authority") if isinstance(metadata, dict) else None
    )
    if not isinstance(authority, dict):
        return None
    if authority.get("contract_id") != VISUAL_EVIDENCE_AUTHORITY_CONTRACT:
        return None
    if str(authority.get("answer") or "").strip() != str(answer or "").strip():
        return None
    selected_ids = set(_page_evidence_ids(bundle))
    evidence_ids = _unique_strings(authority.get("evidence_ids"))
    if not evidence_ids or not set(evidence_ids) <= selected_ids:
        return None
    selected_typed_item_ids = _selected_typed_item_ids(bundle)
    typed_path = authority.get("typed_visual_path")
    if typed_path is not None and not _typed_path_is_selected(
        typed_path,
        selected_typed_item_ids,
    ):
        return None
    return {
        **authority,
        "answer": str(authority["answer"]).strip(),
        "evidence_ids": evidence_ids,
        **({"typed_visual_path": typed_path} if typed_path is not None else {}),
    }


def project_visual_evidence_to_typed_items(
    items: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Project structured OCR/VLM/table output into canonical evidence items."""

    projected = list(items)
    seen = {identity_of(item).key for item in projected}
    added = 0
    rejected = 0
    for parent in items:
        if not _is_visual_parent(parent):
            continue
        for index, extraction in enumerate(_visual_extractions(parent)):
            record = _typed_visual_record(parent, extraction, index)
            if record is None:
                rejected += 1
                continue
            identity = identity_of(record).key
            if identity in seen:
                continue
            seen.add(identity)
            projected.append(record)
            added += 1
    projection = {
        "contract_id": TYPED_VISUAL_EVIDENCE_PATH_CONTRACT,
        "parent_count": sum(_is_visual_parent(item) for item in items),
        "projected_count": added,
        "rejected_count": rejected,
    }
    return projected, projection


def project_visual_evidence(
    items: list[dict[str, Any]], metadata: dict[str, Any]
) -> list[dict[str, Any]]:
    projected, projection = project_visual_evidence_to_typed_items(items)
    metadata["visual_typed_projection"] = projection
    return projected


def typed_visual_evidence_path(bundle: Any) -> dict[str, Any] | None:
    metadata = getattr(bundle, "metadata", None)
    plan = metadata.get("query_plan") if isinstance(metadata, dict) else None
    if not isinstance(plan, dict):
        return None
    slots = plan.get("evidence_slots")
    if not isinstance(slots, list):
        return None
    required = [
        slot
        for slot in slots
        if isinstance(slot, dict)
        and (
            slot.get("required_for_execution") or slot.get("required_for_verification")
        )
        and slot.get("role") in {"operand", "support"}
    ]
    bindings: dict[str, list[str]] = {}
    for slot in required:
        slot_id = str(slot.get("slot_id") or "").strip()
        if not slot_id or str(slot.get("status") or "") != "verified_support":
            return None
        evidence_ids = _unique_strings(slot.get("evidence_ids"))
        if not evidence_ids:
            return None
        bindings[slot_id] = evidence_ids
    required_ids = [str(slot.get("slot_id")) for slot in required]
    if not required_ids or set(bindings) != set(required_ids):
        return None
    selected_typed_ids = _selected_typed_item_ids(bundle)
    if not selected_typed_ids or any(
        evidence_id not in selected_typed_ids
        for values in bindings.values()
        for evidence_id in values
    ):
        return None
    return {
        "contract_id": TYPED_VISUAL_EVIDENCE_PATH_CONTRACT,
        "required_slot_ids": required_ids,
        "verified_support_slot_ids": required_ids,
        "slot_bindings": bindings,
        "query_plan_state_version": int(plan.get("state_version") or 0),
    }


def bridge_element_records_to_page_records(
    page_records: list[dict[str, Any]],
    element_records: list[dict[str, Any]],
    *,
    pipeline: Any | None = None,
    crosswalk: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if not page_records or not element_records:
        return page_records
    resolver = SourceIdentityResolver(
        crosswalk
        if crosswalk is not None
        else _pipeline_source_identity_crosswalk(pipeline)
    )
    by_source_page: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for record in element_records:
        source_page = _source_page(record, resolver)
        if source_page[0] and source_page[1]:
            by_source_page.setdefault(source_page, []).extend(
                _element_visual_extractions(record)
            )
    bridged: list[dict[str, Any]] = []
    for page in page_records:
        source_page = _source_page(page, resolver)
        extractions = by_source_page.get(source_page, [])
        if not extractions:
            bridged.append(page)
            continue
        output = dict(page)
        metadata = dict(output.get("metadata") or {})
        existing = _metadata_visual_extractions(metadata)
        seen = {_visual_extraction_key(item) for item in existing}
        for extraction in extractions:
            key = _visual_extraction_key(extraction)
            if key not in seen:
                existing.append(extraction)
                seen.add(key)
        metadata["visual_extractions"] = existing
        output["metadata"] = metadata
        bridged.append(output)
    return bridged


def _pipeline_source_identity_crosswalk(pipeline: Any | None) -> list[dict[str, Any]]:
    request = getattr(pipeline, "docqa_request", None)
    values = getattr(pipeline, "source_identity_crosswalk", None) or getattr(
        request,
        "source_identity_crosswalk",
        None,
    )
    return [dict(value) for value in values or [] if isinstance(value, dict)]


def _element_visual_extractions(record: dict[str, Any]) -> list[dict[str, Any]]:
    metadata = dict(record.get("metadata") or {})
    output: list[dict[str, Any]] = []
    for key in (
        "visual_extractions",
        "structured_visual_evidence",
        "table_cells",
        "ocr_cells",
        "vlm_cells",
    ):
        values = metadata.get(key)
        if isinstance(values, dict):
            values = (
                values.get("cells") or values.get("elements") or values.get("items")
            )
        if isinstance(values, list):
            output.extend(
                _inherit_element_locator(record, value)
                for value in values
                if isinstance(value, dict)
            )
    return output


def _inherit_element_locator(
    parent: dict[str, Any], extraction: dict[str, Any]
) -> dict[str, Any]:
    return {
        **extraction,
        "file_id": extraction.get("file_id") or parent.get("file_id"),
        "source_id": extraction.get("source_id") or parent.get("source_id"),
        "page_label": extraction.get("page_label") or parent.get("page_label"),
        "parent_element_id": extraction.get("parent_element_id")
        or parent.get("element_id"),
        "source_backrefs": extraction.get("source_backrefs")
        or parent.get("source_backrefs"),
    }


def _metadata_visual_extractions(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    values = metadata.get("visual_extractions")
    if isinstance(values, list):
        return [dict(value) for value in values if isinstance(value, dict)]
    return []


def _visual_extraction_key(extraction: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        str(extraction.get(key) or "").strip()
        for key in ("evidence_id", "cell_id", "span_id", "element_id", "text")
    )


def _source_page(
    record: dict[str, Any],
    resolver: SourceIdentityResolver | None = None,
) -> tuple[str, str]:
    metadata = dict(record.get("metadata") or {})
    source_values = (
        record.get("source_id"),
        record.get("file_id"),
        record.get("document_id"),
        metadata.get("source_id"),
        metadata.get("file_id"),
        record.get("file_name"),
        metadata.get("file_name"),
    )
    source = ""
    for value in source_values:
        if not str(value or "").strip():
            continue
        if resolver is None or not resolver.records:
            source = str(value).strip()
            break
        source = resolver.resolve(value)
        if source:
            break
    return (
        source,
        str(
            record.get("page_label")
            or record.get("page")
            or record.get("page_number")
            or metadata.get("page_label")
            or ""
        ).strip(),
    )


def _page_evidence_ids(bundle: Any) -> list[str]:
    output: list[str] = []
    for item in getattr(bundle, "items", []) or []:
        if not isinstance(item, dict):
            continue
        if (
            str(item.get("modality") or item.get("element_type") or "").lower()
            != "page_image"
        ):
            continue
        if str(item.get("evidence_level") or "").lower() != "page":
            continue
        try:
            evidence_id = identity_of(item).key
        except ValueError:
            continue
        if evidence_id and evidence_id not in output:
            output.append(evidence_id)
    metadata = getattr(bundle, "metadata", None)
    requested = (
        metadata.get("visual_generation_evidence_ids")
        if isinstance(metadata, dict)
        else None
    )
    if isinstance(requested, list):
        return [
            evidence_id
            for evidence_id in _unique_strings(requested)
            if evidence_id in output
        ]
    return output


def _selected_typed_item_ids(bundle: Any) -> set[str]:
    selected: set[str] = set()
    for item in getattr(bundle, "items", []) or []:
        if not isinstance(item, dict) or not _is_typed_visual_item(item):
            continue
        try:
            selected.add(identity_of(item).key)
        except ValueError:
            continue
    return selected


def _typed_path_is_selected(path: Any, selected_ids: set[str]) -> bool:
    if not isinstance(path, dict):
        return False
    required = {
        str(value).strip()
        for value in path.get("required_slot_ids") or []
        if str(value).strip()
    }
    bindings = path.get("slot_bindings")
    if not required or not isinstance(bindings, dict) or set(bindings) != required:
        return False
    return all(
        str(evidence_id).strip() in selected_ids
        for values in bindings.values()
        for evidence_id in values or []
    )


def _is_typed_visual_item(item: dict[str, Any]) -> bool:
    return str(item.get("evidence_level") or "").strip().lower() in {
        "cell",
        "span",
        "element",
    }


def _is_visual_parent(item: dict[str, Any]) -> bool:
    modality = str(item.get("modality") or item.get("element_type") or "").lower()
    return modality in {"page_image", "image", "figure", "slide"}


def _visual_extractions(item: dict[str, Any]) -> list[dict[str, Any]]:
    containers = [item, item.get("metadata") or {}]
    output: list[dict[str, Any]] = []
    for container in containers:
        if not isinstance(container, dict):
            continue
        for key in _VISUAL_EXTRACTION_KEYS:
            value = container.get(key)
            if isinstance(value, dict):
                value = (
                    value.get("cells") or value.get("elements") or value.get("items")
                )
            if isinstance(value, list):
                output.extend(dict(entry) for entry in value if isinstance(entry, dict))
    return output


def _typed_visual_record(
    parent: dict[str, Any], extraction: dict[str, Any], index: int
) -> dict[str, Any] | None:
    parent_metadata = dict(parent.get("metadata") or {})
    value = dict(extraction)
    nested = value.get("metadata")
    if isinstance(nested, dict):
        value = {**nested, **value}
    file_id = str(parent.get("file_id") or parent.get("source_id") or "").strip()
    page_label = str(parent.get("page_label") or parent.get("page") or "").strip()
    if not file_id or not page_label:
        return None
    table_id = str(
        value.get("table_id") or value.get("table_instance_id") or ""
    ).strip()
    cell_id = str(value.get("cell_id") or "").strip()
    row_index = value.get("row_index")
    column_index = value.get("column_index")
    if not cell_id and table_id and row_index is not None and column_index is not None:
        cell_id = f"{table_id}:{row_index}:{column_index}"
    element_id = str(value.get("element_id") or "").strip()
    if not cell_id and not element_id and not str(value.get("span_id") or "").strip():
        element_id = f"visual-extraction-{index}"
    text = str(
        value.get("text") or value.get("ocr_text") or value.get("vlm_text") or ""
    ).strip()
    raw_value = str(value.get("value") or "").strip()
    if not text and not raw_value:
        return None
    record = {
        **parent_metadata,
        **value,
        "file_id": file_id,
        "source_id": file_id,
        "page_label": page_label,
        "element_id": element_id,
        "cell_id": cell_id,
        "evidence_id": str(
            value.get("evidence_id") or f"visual:{file_id}:{page_label}:{index}"
        ),
        "modality": str(value.get("modality") or value.get("element_type") or "table"),
        "evidence_level": (
            "cell" if cell_id else str(value.get("evidence_level") or "element")
        ),
        "text": text or raw_value,
        "ocr_text": str(value.get("ocr_text") or text),
        "vlm_text": str(value.get("vlm_text") or ""),
        "source_backrefs": list(
            value.get("source_backrefs")
            or parent.get("source_backrefs")
            or [f"{file_id}#page:{page_label}"]
        ),
        "parent_element_id": str(
            value.get("parent_element_id") or parent.get("evidence_id") or ""
        ),
    }
    normalized = element_record_from_mapping(
        record,
        default_file_id=file_id,
        default_file_name=str(parent.get("file_name") or ""),
        default_page_label=page_label,
        default_element_id=element_id,
        default_modality=record["modality"],
        default_evidence_id=record["evidence_id"],
    )
    if normalized is None:
        return None
    normalized_metadata = dict(normalized.get("metadata") or {})
    normalized_metadata.update(
        {
            "visual_parent_evidence_id": str(parent.get("evidence_id") or ""),
            "visual_extraction_source": str(
                value.get("extraction_source") or "ocr_vlm_table"
            ),
        }
    )
    normalized["metadata"] = normalized_metadata
    return normalized


def _unique_strings(values: Any) -> list[str]:
    output: list[str] = []
    for value in values or ():
        normalized = str(value or "").strip()
        if normalized and normalized not in output:
            output.append(normalized)
    return output
