from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from .evidence_alias_lookup import unambiguous_evidence_alias_lookup
from .evidence_identity import identity_of
from .finance_scale import source_scale_evidence
from .financial_statement_identity import source_identity
from .financial_table import parse_financial_table_cells_with_context

_RUNTIME_IDENTITY_FIELDS = (
    "evaluation_identity",
    "reranker_backend",
    "reranker_input_identity",
    "reranker_model",
    "reranker_observations",
    "reranker_rank",
    "reranker_score",
    "reranking_score",
    "runtime_identity",
)
_TRANSIENT_METADATA_FIELDS = (
    "evaluation_identity",
    "late_interaction_tokens",
    "representations",
    "caption",
    "ocr_text",
    "vlm_text",
    "reranker_backend",
    "reranker_execution_trace",
    "reranker_execution_traces",
    "reranker_input_identity",
    "reranker_model",
    "reranker_observations",
    "reranker_rank",
    "reranker_score",
    "reranking_score",
    "runtime_identity",
)


def calculation_evidence_lookup(
    items: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return unambiguous_evidence_alias_lookup(calculation_evidence_items(items))


def calculation_evidence_items(
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    expanded: list[dict[str, Any]] = []
    identities: set[str] = set()
    for item in reconcile_materialized_cells(items):
        candidates = [
            item,
            *(
                materialize_financial_cell(item, cell)
                for cell in parse_financial_table_cells_with_context(item, items)
            ),
        ]
        for candidate in candidates:
            identity = identity_of(candidate).key
            if identity in identities:
                continue
            identities.add(identity)
            expanded.append(candidate)
    return expanded


def reconcile_materialized_cells(
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    child_items = [
        (index, item, parent_id)
        for index, item in enumerate(items)
        if (parent_id := _structured_child_parent_id(item))
    ]
    cross_parser_child_items = [
        (index, item, parent_id)
        for index, item in enumerate(items)
        if (parent_id := _logical_child_parent_id(item))
    ]
    if not child_items and not cross_parser_child_items:
        return items
    child_parent_ids = {parent_id for _index, _item, parent_id in child_items}
    parent_cells: dict[int, tuple[Any, ...]] = {}
    cross_parser_parents: list[tuple[dict[str, Any], tuple[Any, ...]]] = []
    replacements: dict[int, dict[str, Any]] = {}
    replacement_ranks: dict[int, tuple[int, int, int, int, int]] = {}
    for parent_index, parent in enumerate(items):
        if _is_cell_item(parent):
            continue
        direct_parent = bool(_parent_aliases(parent) & child_parent_ids)
        cross_parser_parent = any(
            _cross_parser_parent_candidate(child, parent)
            for _index, child, _parent_id in cross_parser_child_items
        )
        if not direct_parent and not cross_parser_parent:
            continue
        cells = parse_financial_table_cells_with_context(parent, items)
        if not cells:
            continue
        if cross_parser_parent:
            cross_parser_parents.append((parent, cells))
        if direct_parent:
            parent_cells[parent_index] = cells
            for child_index, child, parent_id in child_items:
                if parent_id not in _parent_aliases(parent):
                    continue
                cell = _replacement_cell(child, cells)
                if cell is not None:
                    rank = _replacement_rank(child, cell)
                    if rank > replacement_ranks.get(child_index, (-1, -1, -1, -1, -1)):
                        replacement_ranks[child_index] = rank
                        replacements[child_index] = materialize_financial_cell(
                            parent, cell
                        )

    for child_index, child, _parent_id in cross_parser_child_items:
        if child_index in replacements:
            continue
        replacement = _cross_parser_replacement(child, cross_parser_parents)
        if replacement is not None:
            replacements[child_index] = replacement

    if not parent_cells and not replacements:
        return items
    reconciled: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        replacement = replacements.get(index)
        if replacement is not None:
            reconciled.append(replacement)
            continue
        reconciled.append(item)
        parent_cells_for_item = parent_cells.get(index)
        if parent_cells_for_item is not None:
            reconciled.extend(
                materialize_financial_cell(item, cell) for cell in parent_cells_for_item
            )
    return reconciled


def _cross_parser_parent_candidate(
    child: dict[str, Any],
    parent: dict[str, Any],
) -> bool:
    child_source = source_identity(child)
    parent_source = source_identity(parent)
    child_page = _normalized_text(child.get("page_label") or child.get("page"))
    parent_page = _normalized_text(parent.get("page_label") or parent.get("page"))
    return bool(
        not _normalized_text(child.get("scale"))
        and child_source
        and parent_source
        and child_source == parent_source
        and child_page
        and child_page == parent_page
        and _parent_aliases(parent)
    )


def _logical_child_parent_id(item: dict[str, Any]) -> str:
    if str(item.get("evidence_level") or "").strip().lower() != "cell":
        return ""
    if any(
        value in (None, "")
        for value in (
            source_identity(item),
            item.get("page_label") or item.get("page"),
            item.get("row_label"),
            item.get("period") or item.get("column_label"),
            item.get("value"),
        )
    ):
        return ""
    return str(
        item.get("materialization_source_id") or item.get("parent_element_id") or ""
    ).strip()


def _cross_parser_replacement(
    child: dict[str, Any],
    parents: list[tuple[dict[str, Any], tuple[Any, ...]]],
) -> dict[str, Any] | None:
    matches: dict[str, dict[str, Any]] = {}
    for parent, cells in parents:
        for cell in cells:
            if not _cross_parser_atomic_cell_match(child, cell):
                continue
            candidate = materialize_financial_cell(parent, cell)
            if not _local_scale_parent_provenance(candidate, parent, cell.scale):
                continue
            matches[identity_of(candidate).key] = candidate
    if len(matches) != 1:
        return None
    return next(iter(matches.values()))


def _cross_parser_atomic_cell_match(child: dict[str, Any], cell: Any) -> bool:
    if not _is_canonical_cell(cell) or not _normalized_text(cell.scale):
        return False
    required_pairs = (
        (source_identity(child), cell.source_id),
        (child.get("page_label") or child.get("page"), cell.page_label),
        (child.get("row_label"), cell.row_label),
        (child.get("period") or child.get("column_label"), cell.period),
    )
    if any(
        not _normalized_text(left) or _normalized_text(left) != _normalized_text(right)
        for left, right in required_pairs
    ):
        return False
    if not _required_value_match(child.get("value"), cell.value):
        return False
    if any(
        not _compatible_dimension(str(left or ""), str(right or ""))
        for left, right in (
            (child.get("statement_kind"), cell.statement_kind),
            (child.get("financial_scope"), cell.financial_scope),
            (child.get("currency"), cell.currency),
        )
    ):
        return False
    child_coordinates = _item_coordinates(child)
    cell_coordinates = (int(cell.row_index or 0), int(cell.column_index or 0))
    if all(child_coordinates) and all(cell_coordinates):
        return child_coordinates == cell_coordinates
    return _strict_coordinate_free_match(child, cell)


def _strict_coordinate_free_match(child: dict[str, Any], cell: Any) -> bool:
    return bool(
        _normalized_text(child.get("column_label"))
        and _normalized_text(child.get("column_label"))
        == _normalized_text(cell.column_label)
        and all(
            _normalized_text(left) and _normalized_text(left) == _normalized_text(right)
            for left, right in (
                (child.get("statement_kind"), cell.statement_kind),
                (child.get("financial_scope"), cell.financial_scope),
                (child.get("currency"), cell.currency),
            )
        )
    )


def _local_scale_parent_provenance(
    candidate: dict[str, Any],
    parent: dict[str, Any],
    expected_scale: str,
) -> bool:
    scale, evidence_id = source_scale_evidence(candidate, [parent, candidate])
    return bool(
        _normalized_text(scale) == _normalized_text(expected_scale)
        and evidence_id
        and evidence_id in _parent_aliases(parent)
        and candidate.get("materialization_source_id")
    )


def _required_value_match(left: Any, right: Any) -> bool:
    return (
        left not in (None, "")
        and right not in (None, "")
        and _compatible_value(left, right)
    )


def _item_coordinates(item: dict[str, Any]) -> tuple[int, int]:
    physical = item.get("physical_cell_identity")
    nested = physical if isinstance(physical, dict) else {}
    return (
        int(item.get("row_index") or nested.get("row_index") or 0),
        int(item.get("column_index") or nested.get("column_index") or 0),
    )


def _replacement_cell(
    child: dict[str, Any],
    cells: tuple[Any, ...],
) -> Any | None:
    semantic_cells = [
        cell
        for cell in cells
        if _is_canonical_cell(cell) and _semantic_cell_match(child, cell)
    ]
    if not semantic_cells:
        return None
    physical_cells = [
        cell for cell in semantic_cells if _coordinates_match(child, cell)
    ]
    if physical_cells:
        compatible = [
            cell for cell in physical_cells if _strict_cell_match(child, cell)
        ]
    elif child.get("physical_cell_identity"):
        compatible = []
    else:
        value_evidence = [
            cell
            for cell in semantic_cells
            if _compatible_value(child.get("value"), cell.value)
            and _compatible_dimension(str(child.get("scale") or ""), cell.scale)
        ]
        compatible = [
            cell for cell in semantic_cells if _scope_scale_match(child, cell)
        ]
        if not value_evidence or not compatible:
            compatible = []
    if not compatible:
        return None
    return max(compatible, key=lambda cell: _replacement_rank(child, cell))


def _semantic_cell_match(child: dict[str, Any], cell: Any) -> bool:
    return (
        _physical_base_match(child, cell)
        and _normalized_text(child.get("row_label")) == _normalized_text(cell.row_label)
        and _normalized_period(child.get("period") or child.get("column_label"))
        == _normalized_period(cell.period)
        and _compatible_dimension(
            str(child.get("statement_kind") or ""), cell.statement_kind
        )
    )


def _strict_cell_match(child: dict[str, Any], cell: Any) -> bool:
    return _scope_scale_match(child, cell) and _compatible_value(
        child.get("value"), cell.value
    )


def _scope_scale_match(child: dict[str, Any], cell: Any) -> bool:
    return _compatible_dimension(
        str(child.get("financial_scope") or ""), cell.financial_scope
    ) and _compatible_dimension(str(child.get("scale") or ""), cell.scale)


def _physical_base_match(child: dict[str, Any], cell: Any) -> bool:
    for child_value, cell_value in (
        (source_identity(child), cell.source_id),
        (child.get("page_label") or child.get("page"), cell.page_label),
        (
            child.get("table_instance_id") or child.get("table_id"),
            cell.table_instance_id,
        ),
        (child.get("block_id"), cell.block_id),
        (child.get("table_id"), cell.table_id),
    ):
        if (
            child_value
            and cell_value
            and _normalized_text(child_value) != _normalized_text(cell_value)
        ):
            return False
    return True


def _coordinates_match(child: dict[str, Any], cell: Any) -> bool:
    return (
        int(child.get("row_index") or 0) == cell.row_index
        and int(child.get("column_index") or 0) == cell.column_index
    )


def _replacement_rank(
    child: dict[str, Any], cell: Any
) -> tuple[int, int, int, int, int]:
    child_scope = _normalized_text(child.get("financial_scope"))
    child_scale = _normalized_text(child.get("scale"))
    return (
        int(
            bool(child_scope)
            and _compatible_dimension(child_scope, cell.financial_scope)
        ),
        int(not child_scale or _compatible_dimension(child_scale, cell.scale)),
        int(_compatible_value(child.get("value"), cell.value)),
        int(_normalized_text(cell.financial_scope) == "consolidated"),
        len(cell.column_header_path),
    )


def _compatible_dimension(left: str, right: str) -> bool:
    return not left or not right or _normalized_text(left) == _normalized_text(right)


def _compatible_value(left: Any, right: Any) -> bool:
    if left in (None, "") or right in (None, ""):
        return True
    try:
        return Decimal(str(left).replace(",", "")) == Decimal(str(right))
    except InvalidOperation:
        return _normalized_text(left) == _normalized_text(right)


def _normalized_text(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()


def _normalized_period(value: Any) -> str:
    return re.sub(r"^fy\s*", "", _normalized_text(value))


def _is_cell_item(item: dict[str, Any]) -> bool:
    return bool(
        str(item.get("evidence_level") or "").strip().lower() == "cell"
        or str(item.get("cell_id") or "").strip()
    )


def _is_canonical_cell(cell: Any) -> bool:
    return bool(
        str(getattr(cell, "cell_id", "") or "").strip()
        and str(getattr(cell, "row_label", "") or "").strip()
        and str(getattr(cell, "period", "") or "").strip()
        and int(getattr(cell, "row_index", 0) or 0) > 0
        and int(getattr(cell, "column_index", 0) or 0) > 0
    )


def _structured_child_parent_id(item: dict[str, Any]) -> str:
    if str(item.get("evidence_level") or "").strip().lower() != "cell":
        return ""
    if not int(item.get("row_index") or 0) or not int(item.get("column_index") or 0):
        return ""
    return str(
        item.get("materialization_source_id") or item.get("parent_element_id") or ""
    ).strip()


def _parent_aliases(item: dict[str, Any]) -> set[str]:
    return {
        str(item.get(field) or "").strip()
        for field in (
            "evidence_id",
            "canonical_id",
            "element_id",
            "table_id",
            "table_instance_id",
        )
        if str(item.get(field) or "").strip()
    }


def materialize_financial_cell(item: dict[str, Any], cell: Any) -> dict[str, Any]:
    materialized = dict(item)
    materialized.pop("identity", None)
    materialized.pop("canonical_id", None)
    _drop_fields(materialized, _RUNTIME_IDENTITY_FIELDS)
    parent_evidence_id = str(
        item.get("evidence_id")
        or item.get("canonical_id")
        or item.get("element_id")
        or ""
    ).strip()
    materialized.update(
        {
            "evidence_id": cell.cell_id,
            "cell_id": cell.cell_id,
            "source_id": cell.source_id,
            "file_id": cell.source_id or item.get("file_id") or "",
            "cell_role": cell.cell_role,
            "evidence_level": "cell",
            "table_id": cell.table_id,
            "table_instance_id": cell.table_instance_id,
            "table_group_id": cell.table_group_id,
            "block_id": cell.block_id,
            "physical_cell_identity": cell.physical_identity.as_dict(),
            "semantic_cell_key": cell.semantic_key.as_dict(),
            "parent_element_id": cell.table_id,
            "materialization_source_id": parent_evidence_id,
            "row_index": cell.row_index,
            "column_index": cell.column_index,
            "row_label": cell.row_label,
            "column_label": cell.column_label,
            "period": cell.period,
            "period_kind": cell.period_kind,
            "value": str(cell.value),
            "unit": cell.unit,
            "scale": cell.scale,
            "currency": cell.currency,
            "statement_kind": cell.statement_kind,
            "financial_scope": cell.financial_scope,
            "text": cell.verification_text(),
            "caption": cell.row_label,
            "ocr_text": "",
            "vlm_text": "",
            "representations": [],
        }
    )
    metadata = dict(materialized.get("metadata") or {})
    if cell.column_header_path:
        metadata["column_header_path"] = list(cell.column_header_path)
    if cell.cell_id_aliases:
        metadata["cell_id_aliases"] = list(cell.cell_id_aliases)
    _drop_fields(metadata, _TRANSIENT_METADATA_FIELDS)
    materialized["metadata"] = metadata
    materialized["canonical_id"] = identity_of(materialized).key
    return materialized


def _drop_fields(payload: dict[str, Any], fields: tuple[str, ...]) -> None:
    for field in fields:
        payload.pop(field, None)


def calculation_operand_identity(item: dict[str, Any], operand: Any) -> str:
    if operand.cell_id:
        return cell_identity(item, operand.cell_id)
    return identity_of(item).key


def cell_identity(item: dict[str, Any], cell_id: str) -> str:
    payload = dict(item)
    payload.pop("identity", None)
    payload.pop("canonical_id", None)
    payload["cell_id"] = cell_id
    payload["evidence_level"] = "cell"
    return identity_of(payload).key


def same_source(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if identity_of(left).key == identity_of(right).key:
        return True
    if _explicit_parent_child_lineage(left, right):
        return True
    left_source = _source_id(left)
    right_source = _source_id(right)
    return bool(left_source and left_source == right_source)


def _explicit_parent_child_lineage(
    left: dict[str, Any],
    right: dict[str, Any],
) -> bool:
    for child, parent in ((left, right), (right, left)):
        parent_id = str(child.get("materialization_source_id") or "").strip()
        parent_aliases = {
            str(parent.get(field) or "").strip()
            for field in ("evidence_id", "canonical_id", "element_id")
            if str(parent.get(field) or "").strip()
        }
        if parent_id and parent_id in parent_aliases:
            return True
    return False


def _source_id(item: dict[str, Any]) -> str:
    return source_identity(item)
