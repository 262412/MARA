from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Any

from .calculation_evidence_identity import calculation_evidence_items
from .evidence_identity import exact_evidence_aliases, identity_of
from .finance_segment_table import (
    revenue_section_item,
    segment_title,
    vertical_segment_matrix,
)
from .financial_statement_identity import financial_statement_identity
from .financial_table import parse_financial_table_cells

FINANCE_SEGMENT_COMPARISON_CONTRACT = "finance_segment_comparison.v1"


@dataclass(frozen=True)
class FinanceSegmentComparisonAnswer:
    answer: str
    status: str
    periods: tuple[str, str]
    excluded_entities: tuple[str, ...]
    entity_period_values: dict[str, dict[str, str]]
    proportional_changes: dict[str, str]
    citation_ids: tuple[str, ...]
    entity_period_cell_ids: dict[str, dict[str, str]]
    unit: str
    scale: str
    matrix_evidence_ids: tuple[str, ...]
    audit_status: str
    contract_id: str = FINANCE_SEGMENT_COMPARISON_CONTRACT

    def as_trace(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["periods"] = list(self.periods)
        payload["excluded_entities"] = list(self.excluded_entities)
        payload["citation_ids"] = list(self.citation_ids)
        payload["matrix_evidence_ids"] = list(self.matrix_evidence_ids)
        return payload


@dataclass(frozen=True)
class _SegmentMatrix:
    values: dict[str, dict[str, Decimal]]
    cell_ids: dict[str, dict[str, str]]
    citation_ids: tuple[str, ...]
    item_ids: tuple[str, ...]
    unit: str
    scale: str
    source_page: tuple[str, str]
    table_lineage: str


def finance_segment_comparison_answer(
    question: str,
    evidence_items: list[dict[str, Any]],
    *,
    query_plan: dict[str, Any] | None = None,
) -> FinanceSegmentComparisonAnswer | None:
    if not _is_segment_comparison(question):
        return None
    evidence_items = segment_comparison_evidence_items(evidence_items)
    periods = _question_periods(question)
    excluded = _excluded_entities(question)
    if len(periods) != 2:
        return _empty_result("missing_periods", periods, excluded)
    compatible_items = _query_plan_items(query_plan, evidence_items, periods)
    matrices = _coherent_segment_matrices(compatible_items, periods, excluded)
    if not matrices:
        return _empty_result("insufficient_entities", periods, excluded)
    if len(matrices) != 1:
        return _empty_result("ambiguous_matrix", periods, excluded)
    matrix = matrices[0]
    complete = matrix.values

    prior_period, current_period = periods
    changes = {
        entity: (
            (period_values[current_period] - period_values[prior_period])
            / abs(period_values[prior_period])
        )
        for entity, period_values in complete.items()
        if period_values[prior_period] != 0
    }
    if len(changes) < 2:
        return _result(
            "",
            "invalid_denominator",
            periods,
            excluded,
            complete,
            changes,
            matrix.citation_ids,
            matrix.cell_ids,
            matrix.unit,
            matrix.scale,
            matrix.item_ids,
        )
    answer = max(changes, key=changes.__getitem__)
    return _result(
        answer,
        "ok",
        periods,
        excluded,
        complete,
        changes,
        matrix.citation_ids,
        matrix.cell_ids,
        matrix.unit,
        matrix.scale,
        matrix.item_ids,
    )


def segment_comparison_evidence_items(
    evidence_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    revenue_items = [
        item
        if item.get("cell_id")
        or str(item.get("evidence_level") or "").lower() == "cell"
        else revenue_section_item(item) or item
        for item in evidence_items
    ]
    expanded = calculation_evidence_items(revenue_items)
    cells = [
        item
        for item in expanded
        if item.get("cell_id")
        or str(item.get("evidence_level") or "").lower() == "cell"
    ]
    return cells or expanded


def coherent_segment_evidence_items(
    query_plan: Any,
    evidence_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return only one complete, same-table segment revenue matrix.

    This is used before ordinary slot ranking so a consolidated total, an
    incomplete period row, or cells from unrelated tables cannot satisfy the
    authoritative comparison plan.
    """

    plan = query_plan.as_dict() if hasattr(query_plan, "as_dict") else query_plan
    plan = dict(plan or {})
    if (
        plan.get("constraints", {}).get("comparison_operator")
        != "proportional_increase"
    ):
        return list(evidence_items)
    periods = tuple(
        str(value) for value in plan.get("constraints", {}).get("periods") or ()
    )
    excluded = tuple(
        _title(str(value))
        for value in plan.get("constraints", {}).get("excluded_entities") or ()
    )
    matrices = _coherent_segment_matrices(evidence_items, periods, excluded)
    if len(matrices) != 1:
        return []
    allowed = set(matrices[0].item_ids)
    return [item for item in evidence_items if identity_of(item).key in allowed]


def _coherent_segment_matrices(
    evidence_items: list[dict[str, Any]],
    periods: tuple[str, ...],
    excluded: tuple[str, ...],
) -> list[_SegmentMatrix]:
    matrices: list[_SegmentMatrix] = []
    for group in _segment_evidence_groups(evidence_items):
        matrix = _matrix_from_group(group, periods, excluded)
        if matrix is not None:
            matrices.append(matrix)
    unique: dict[tuple[Any, ...], _SegmentMatrix] = {}
    for matrix in matrices:
        signature = (
            matrix.source_page,
            matrix.table_lineage,
            tuple(
                (entity, tuple(sorted(values.items())))
                for entity, values in sorted(matrix.values.items())
            ),
        )
        unique.setdefault(signature, matrix)
    return list(unique.values())


def _matrix_from_group(
    items: list[dict[str, Any]],
    periods: tuple[str, ...],
    excluded: tuple[str, ...],
) -> _SegmentMatrix | None:
    values: dict[str, dict[str, Decimal]] = {}
    cell_ids: dict[str, dict[str, str]] = {}
    citations: list[str] = []
    item_ids: list[str] = []
    dimensions: set[tuple[str, str]] = set()
    conflicts = False
    for item in items:
        statement_kind, scope = financial_statement_identity(item)
        if statement_kind and statement_kind != "segment_table":
            continue
        if scope and scope != "segment":
            continue
        section = revenue_section_item(item)
        explicit_cell = bool(
            item.get("cell_id") or item.get("evidence_level") == "cell"
        )
        if section is None and not explicit_cell:
            continue
        parsed_item = section or item
        item_identity = identity_of(item).key
        observed = False
        for cell in parse_financial_table_cells(parsed_item):
            if cell.period not in periods or _is_total_row(cell.row_label):
                continue
            entity = _entity_label(cell.row_label)
            if not _valid_segment_entity(entity) or _excluded(entity, excluded):
                continue
            if not _segment_dimension_provenance(item, cell):
                continue
            observed = True
            dimensions.add((cell.unit or cell.currency, cell.scale))
            prior = values.setdefault(entity, {}).get(cell.period)
            if prior is not None and prior != cell.value:
                conflicts = True
                continue
            values[entity][cell.period] = cell.value
            cell_ids.setdefault(entity, {})[cell.period] = cell.cell_id
        if not observed and section is not None:
            observed, vertical_conflict = _merge_vertical_item(
                section,
                periods,
                excluded,
                values,
                cell_ids,
                dimensions,
            )
            conflicts = conflicts or vertical_conflict
        if observed:
            citation_id = _item_id(item)
            if citation_id and citation_id not in citations:
                citations.append(citation_id)
            if item_identity not in item_ids:
                item_ids.append(item_identity)
    complete = {
        entity: period_values
        for entity, period_values in values.items()
        if all(period in period_values for period in periods)
    }
    complete_cells = {entity: cell_ids[entity] for entity in complete}
    if conflicts or len(complete) < 2 or len(dimensions) != 1:
        return None
    unit, scale = next(iter(dimensions))
    if not scale:
        return None
    return _SegmentMatrix(
        values=complete,
        cell_ids=complete_cells,
        citation_ids=tuple(citations),
        item_ids=tuple(item_ids),
        unit=unit,
        scale=scale,
        source_page=_source_page(items[0]),
        table_lineage=_table_lineage(items[0]),
    )


def _segment_dimension_provenance(item: dict[str, Any], cell: Any) -> bool:
    return bool(
        cell.scale
        and ((cell.unit or cell.currency) or item.get("materialization_source_id"))
    )


def _merge_vertical_item(
    item: dict[str, Any],
    periods: tuple[str, ...],
    excluded: tuple[str, ...],
    values: dict[str, dict[str, Decimal]],
    cell_ids: dict[str, dict[str, str]],
    dimensions: set[tuple[str, str]],
) -> tuple[bool, bool]:
    vertical_values, vertical_ids, unit, scale = vertical_segment_matrix(item, periods)
    if not unit or not scale:
        return False, False
    observed = False
    conflicts = False
    for entity, period_values in vertical_values.items():
        if _excluded(entity, excluded):
            continue
        observed = True
        dimensions.add((unit, scale))
        for period, value in period_values.items():
            prior = values.setdefault(entity, {}).get(period)
            if prior is not None and prior != value:
                conflicts = True
                continue
            values[entity][period] = value
            cell_ids.setdefault(entity, {})[period] = vertical_ids[entity][period]
    return observed, conflicts


def _source_page(item: dict[str, Any]) -> tuple[str, str]:
    metadata = item.get("metadata")
    nested = metadata if isinstance(metadata, dict) else {}
    return (
        str(item.get("source_id") or nested.get("source_id") or ""),
        str(item.get("page_label") or nested.get("page_label") or ""),
    )


def _segment_evidence_groups(
    evidence_items: list[dict[str, Any]],
) -> list[list[dict[str, Any]]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = {}
    for item in evidence_items:
        metadata = item.get("metadata")
        nested = metadata if isinstance(metadata, dict) else {}
        source_id = str(item.get("source_id") or nested.get("source_id") or "")
        page_label = str(item.get("page_label") or nested.get("page_label") or "")
        lineage = _table_lineage(item)
        groups.setdefault((source_id, page_label, lineage), []).append(item)
    return list(groups.values())


def _table_lineage(item: dict[str, Any]) -> str:
    metadata = item.get("metadata")
    nested = metadata if isinstance(metadata, dict) else {}
    table_lineage = tuple(
        (label, str(value))
        for label, value in (
            ("group", item.get("table_group_id") or nested.get("table_group_id")),
            (
                "instance",
                item.get("table_instance_id") or nested.get("table_instance_id"),
            ),
            ("table", item.get("table_id") or nested.get("table_id")),
        )
        if value
    )
    if table_lineage:
        return "|".join(f"{label}:{value}" for label, value in table_lineage)
    parent = str(
        item.get("parent_element_id") or item.get("materialization_source_id") or ""
    )
    return f"parent:{parent}" if parent else f"unscoped:{identity_of(item).key}"


def _result(
    answer: str,
    status: str,
    periods: tuple[str, ...],
    excluded: tuple[str, ...],
    values: dict[str, dict[str, Decimal]],
    changes: dict[str, Decimal],
    citation_ids: tuple[str, ...],
    cell_ids: dict[str, dict[str, str]],
    unit: str,
    scale: str,
    matrix_evidence_ids: tuple[str, ...],
) -> FinanceSegmentComparisonAnswer:
    normalized_periods = (periods[0], periods[1]) if len(periods) >= 2 else ("", "")
    return FinanceSegmentComparisonAnswer(
        answer=answer,
        status=status,
        periods=normalized_periods,
        excluded_entities=excluded,
        entity_period_values={
            entity: {period: str(value) for period, value in period_values.items()}
            for entity, period_values in values.items()
        },
        proportional_changes={
            entity: str(change) for entity, change in changes.items()
        },
        citation_ids=citation_ids,
        entity_period_cell_ids=cell_ids,
        unit=unit,
        scale=scale,
        matrix_evidence_ids=matrix_evidence_ids,
        audit_status="passed" if status == "ok" else "failed",
    )


def _empty_result(
    status: str,
    periods: tuple[str, ...],
    excluded: tuple[str, ...],
) -> FinanceSegmentComparisonAnswer:
    return _result("", status, periods, excluded, {}, {}, (), {}, "", "", ())


def _query_plan_items(
    query_plan: dict[str, Any] | None,
    evidence_items: list[dict[str, Any]],
    periods: tuple[str, ...],
) -> list[dict[str, Any]]:
    plan = dict(query_plan or {})
    if not plan:
        return list(evidence_items)
    constraints = dict(plan.get("constraints") or {})
    slots = [dict(slot) for slot in plan.get("evidence_slots") or []]
    if constraints.get("comparison_operator") != "proportional_increase":
        return []
    if {str(slot.get("period") or "") for slot in slots} != set(periods):
        return []
    if any(
        str(slot.get("statement_kind") or "") != "segment_table"
        or str(slot.get("financial_scope") or "") != "segment"
        or str(slot.get("metric") or "") not in {"net sales", "revenue"}
        for slot in slots
    ):
        return []
    bound_ids = {
        str(evidence_id)
        for slot in slots
        for evidence_id in slot.get("evidence_ids") or []
        if str(evidence_id or "").strip()
    }
    if not bound_ids:
        return []
    return [item for item in evidence_items if bound_ids & exact_evidence_aliases(item)]


def _question_periods(question: str) -> tuple[str, ...]:
    values = []
    for full, short in re.findall(
        r"\b(?:fy\s*)?((?:19|20)\d{2})\b|\bfy\s*(\d{2})\b",
        str(question or ""),
        flags=re.IGNORECASE,
    ):
        values.append(full or f"20{short}")
    return tuple(sorted(dict.fromkeys(values)))


def _excluded_entities(question: str) -> tuple[str, ...]:
    match = re.search(
        r"\bexcluding\s+([a-z][a-z0-9 &-]*?)(?:,|\bin\b|\bwhich\b|$)",
        str(question or "").lower(),
    )
    if not match:
        return ()
    return tuple(_title(value) for value in match.group(1).split(" and ") if value)


def _is_segment_comparison(question: str) -> bool:
    lowered = str(question or "").lower()
    return (
        "segment" in lowered
        and "proportion" in lowered
        and bool(re.search(r"\b(?:most|least|largest|smallest)\b", lowered))
    )


def _entity_label(row_label: str) -> str:
    value = re.sub(
        r"\b(?:net\s+)?(?:sales|revenue|revenues)\b",
        "",
        str(row_label or ""),
        flags=re.IGNORECASE,
    ).strip(" :-")
    return _title(value)


def _title(value: str) -> str:
    return segment_title(value)


def _excluded(entity: str, excluded: tuple[str, ...]) -> bool:
    lowered = entity.lower()
    return any(value.lower() in lowered for value in excluded)


def _is_total_row(row_label: str) -> bool:
    return str(row_label or "").strip().lower().startswith("total")


def _valid_segment_entity(entity: str) -> bool:
    lowered = str(entity or "").strip().lower()
    if not lowered or len(lowered) > 64:
        return False
    return not any(
        phrase in lowered
        for phrase in (
            "each of the",
            "months ended",
            "period ended",
            "year ended",
            "december",
            "september",
            "june",
            "march",
        )
    )


def _item_id(item: dict[str, Any]) -> str:
    return str(
        item.get("materialization_source_id")
        or item.get("evidence_id")
        or item.get("element_id")
        or item.get("canonical_id")
        or ""
    ).strip()
