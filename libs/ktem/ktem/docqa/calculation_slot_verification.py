from __future__ import annotations

from collections.abc import Callable
from typing import Any

from .finance_query_planning import finance_metric_evidence_matches
from .financial_statement_identity import financial_statement_identity
from .query_plan_schema import slot_binding_state


def verify_required_calculation_slots(
    operands: tuple[Any, ...],
    evidence_by_id: dict[str, dict[str, Any]],
    required_slots: list[dict[str, Any]],
    *,
    evidence_text: Callable[[dict[str, Any]], str],
) -> tuple[list[str], list[str], list[str]]:
    slots = [
        slot
        for slot in required_slots
        if bool(
            slot.get(
                "required_for_execution",
                str(slot.get("role") or "support") in {"operand", "dimension"},
            )
        )
    ]
    required_ids = [str(slot.get("slot_id") or "") for slot in slots]
    verified_ids: list[str] = []
    errors: list[str] = []
    used_operands: set[str] = set()
    used_evidence_identities: set[str] = set()
    exact_lineage = any(
        str(getattr(operand, "query_slot_id", "") or "").strip() for operand in operands
    )
    for slot, slot_id in zip(slots, required_ids):
        if str(slot.get("role") or "support") == "dimension":
            if _dimension_matches_slot(operands, slot, evidence_by_id):
                verified_ids.append(slot_id)
            else:
                errors.append(f"required_slot_missing:{slot_id}")
            continue
        cardinality = max(1, int(slot.get("cardinality") or 1))
        matching_operands = _matching_operands(
            operands,
            slot,
            slot_id,
            evidence_by_id,
            used_operands=used_operands,
            used_evidence_identities=used_evidence_identities,
            exact_lineage=exact_lineage,
            evidence_text=evidence_text,
        )
        if len(matching_operands) < cardinality:
            errors.append(f"required_slot_missing:{slot_id}")
            continue
        selected_operands = matching_operands[:cardinality]
        operand_evidence_ids = [
            str(
                getattr(operand, "evidence_identity", "")
                or getattr(operand, "evidence_id", "")
                or ""
            ).strip()
            for operand in selected_operands
        ]
        state_slot = {
            **slot,
            "status": "filled",
            "evidence_ids": operand_evidence_ids,
        }
        if slot_binding_state(state_slot, list(evidence_by_id.values())) != "filled":
            errors.append(f"required_slot_missing:{slot_id}")
            continue
        used_operands.update(operand.operand_id for operand in selected_operands)
        used_evidence_identities.update(
            identity
            for identity in (
                _operand_evidence_identity(operand) for operand in selected_operands
            )
            if identity
        )
        verified_ids.append(slot_id)
    return required_ids, verified_ids, errors


def _matching_operands(
    operands: tuple[Any, ...],
    slot: dict[str, Any],
    slot_id: str,
    evidence_by_id: dict[str, dict[str, Any]],
    *,
    used_operands: set[str],
    used_evidence_identities: set[str],
    exact_lineage: bool,
    evidence_text: Callable[[dict[str, Any]], str],
) -> list[Any]:
    return [
        candidate
        for candidate in operands
        if candidate.operand_id not in used_operands
        and (
            not _operand_evidence_identity(candidate)
            or _operand_evidence_identity(candidate) not in used_evidence_identities
        )
        and (
            not exact_lineage
            or str(getattr(candidate, "query_slot_id", "") or "") == slot_id
        )
        and _operand_matches_slot(
            candidate,
            slot,
            evidence_by_id,
            evidence_text=evidence_text,
        )
    ]


def _operand_evidence_identity(operand: Any) -> str:
    return str(
        getattr(operand, "evidence_identity", "")
        or getattr(operand, "evidence_id", "")
        or ""
    ).strip()


def _dimension_matches_slot(
    operands: tuple[Any, ...],
    slot: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
) -> bool:
    evidence_ids = {
        str(value or "").strip()
        for value in slot.get("evidence_ids") or []
        if str(value or "").strip()
    }
    if not evidence_ids or any(
        evidence_by_id.get(evidence_id) is None for evidence_id in evidence_ids
    ):
        return False
    if slot_binding_state(slot, list(evidence_by_id.values())) != "filled":
        return False
    dimension = str(slot.get("slot_id") or "").lower().rsplit(":", 1)[-1]
    raw_dimension_values = [
        str(getattr(operand, dimension, "") or "").strip().lower()
        for operand in operands
    ]
    if not raw_dimension_values or any(not value for value in raw_dimension_values):
        return False
    dimension_values = set(raw_dimension_values)
    required_value = str(slot.get(dimension) or "").strip().lower()
    if len(dimension_values) != 1 or (
        required_value and dimension_values != {required_value}
    ):
        return False
    for operand in operands:
        value = str(getattr(operand, dimension, "") or "").strip().lower()
        if required_value and value != required_value:
            continue
        if not value:
            continue
        operand_evidence_ids = {
            str(identifier or "").strip()
            for identifier in (
                operand.evidence_identity,
                operand.evidence_id,
                operand.scale_evidence_identity,
                operand.scale_evidence_id,
            )
            if str(identifier or "").strip()
        }
        if evidence_ids & operand_evidence_ids:
            return True
        if any(
            evidence_by_id.get(slot_evidence_id)
            is evidence_by_id.get(operand_evidence_id)
            for slot_evidence_id in evidence_ids
            for operand_evidence_id in operand_evidence_ids
        ):
            return True
    return False


def _operand_matches_slot(
    operand: Any,
    slot: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
    *,
    evidence_text: Callable[[dict[str, Any]], str],
) -> bool:
    period = str(slot.get("period") or "").strip()
    if period and operand.period != period:
        return False
    item = evidence_by_id.get(operand.evidence_identity or operand.evidence_id)
    if item is None:
        return False
    statement_kind, financial_scope = financial_statement_identity(item)
    required_statement_kind = str(slot.get("statement_kind") or "").strip()
    required_scope = str(slot.get("financial_scope") or "").strip()
    if required_statement_kind and statement_kind != required_statement_kind:
        return False
    if required_scope and financial_scope != required_scope:
        return False
    metric = str(slot.get("metric") or "").strip().lower()
    metric_text = " ".join((operand.row_label, evidence_text(item)))
    return not metric or finance_metric_evidence_matches(metric, metric_text)
