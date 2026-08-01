from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from decimal import Decimal, DivisionByZero, InvalidOperation, localcontext
from typing import Any

from .calculation_evidence_identity import (
    calculation_evidence_lookup,
    calculation_operand_identity,
    same_source,
)
from .calculation_slot_verification import verify_required_calculation_slots
from .evidence_identity import identity_of
from .finance_scale import compatible_dimension_scope
from .financial_statement_identity import financial_statement_identity
from .query_evidence_constraints import (
    period_kind_conflicts,
    requires_atomic_calculation_binding,
)

CALCULATION_PLAN_CONTRACT = "calculation_plan.v1"
ALLOWED_OPERATORS = {
    "add",
    "subtract",
    "multiply",
    "divide",
    "ratio",
    "percent_change",
    "percentage_of",
    "average",
    "weighted_average",
}
_SCALE_FACTORS = {
    "": Decimal("1"),
    "one": Decimal("1"),
    "thousand": Decimal("1000"),
    "million": Decimal("1000000"),
    "billion": Decimal("1000000000"),
}
_NUMBER_RE = re.compile(
    r"(?:\$?\s*\([+-]?\d[\d,]*(?:\.\d+)?\)|\(?[+-]?\$?\s*\d[\d,]*(?:\.\d+)?\)?)"
)


@dataclass(frozen=True)
class CalculationOperand:
    operand_id: str
    evidence_id: str
    value: Decimal
    query_slot_id: str = ""
    evidence_identity: str = ""
    source_id: str = ""
    unit: str = ""
    scale: str = ""
    currency: str = ""
    period: str = ""
    period_kind: str = ""
    entity: str = ""
    source: str = "evidence"
    cell_id: str = ""
    row_label: str = ""
    column_label: str = ""
    scale_evidence_id: str = ""
    scale_evidence_identity: str = ""
    statement_kind: str = ""
    financial_scope: str = ""
    table_instance_id: str = ""
    table_group_id: str = ""
    dimension_binding_scope: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["value"] = str(self.value)
        for field_name in (
            "cell_id",
            "query_slot_id",
            "evidence_identity",
            "source_id",
            "row_label",
            "column_label",
            "period_kind",
            "scale_evidence_id",
            "scale_evidence_identity",
            "statement_kind",
            "financial_scope",
            "table_instance_id",
            "table_group_id",
            "dimension_binding_scope",
        ):
            if not payload[field_name]:
                payload.pop(field_name)
        return payload


@dataclass(frozen=True)
class CalculationStep:
    step_id: str
    operator: str
    input_ids: tuple[str, ...]
    constant: Decimal | None = None
    constant_source: str = ""
    rounding_places: int | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["input_ids"] = list(self.input_ids)
        payload["constant"] = None if self.constant is None else str(self.constant)
        return payload


@dataclass(frozen=True)
class CalculationPlan:
    operands: tuple[CalculationOperand, ...]
    steps: tuple[CalculationStep, ...]
    result_step_id: str
    answer_unit: str = ""
    answer_scale: str = ""
    contract_id: str = CALCULATION_PLAN_CONTRACT

    def as_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "operands": [operand.as_dict() for operand in self.operands],
            "steps": [step.as_dict() for step in self.steps],
            "result_step_id": self.result_step_id,
            "answer_unit": self.answer_unit,
            "answer_scale": self.answer_scale,
        }


@dataclass(frozen=True)
class CalculationExecution:
    status: str
    value: Decimal | None
    citation_ids: tuple[str, ...] = ()
    step_values: dict[str, str] = field(default_factory=dict)
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "value": None if self.value is None else str(self.value),
            "citation_ids": list(self.citation_ids),
            "step_values": dict(self.step_values),
            "error": self.error,
        }


@dataclass(frozen=True)
class CalculationVerification:
    valid: bool
    errors: tuple[str, ...] = ()
    verified_operand_ids: tuple[str, ...] = ()
    citation_ids: tuple[str, ...] = ()
    required_slot_ids: tuple[str, ...] = ()
    verified_required_slot_ids: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def execute_calculation_plan(plan: CalculationPlan) -> CalculationExecution:
    structural_errors = _structural_errors(plan, question="")
    if structural_errors:
        return CalculationExecution(
            status="error",
            value=None,
            error=structural_errors[0],
        )
    values = {
        operand.operand_id: operand.value * _scale_factor(operand.scale)
        for operand in plan.operands
    }
    step_values: dict[str, str] = {}
    try:
        with localcontext() as context:
            context.prec = 34
            for step in plan.steps:
                inputs = [values[input_id] for input_id in step.input_ids]
                value = _execute_step(step, inputs)
                if step.rounding_places is not None:
                    quantum = Decimal("1").scaleb(-step.rounding_places)
                    value = value.quantize(quantum)
                values[step.step_id] = value
                step_values[step.step_id] = str(value)
    except (DivisionByZero, ZeroDivisionError):
        return CalculationExecution(
            status="error",
            value=None,
            step_values=step_values,
            error=f"division_by_zero:{step.step_id}",
        )
    except (InvalidOperation, ValueError) as exc:
        return CalculationExecution(
            status="error",
            value=None,
            step_values=step_values,
            error=f"calculation_error:{step.step_id}:{type(exc).__name__}",
        )

    result = values[plan.result_step_id]
    if plan.answer_scale and plan.answer_unit.lower() not in {"percent", "%", "ratio"}:
        result /= _scale_factor(plan.answer_scale)
    citations = tuple(
        dict.fromkeys(
            evidence_id
            for operand in plan.operands
            if operand.source == "evidence"
            for evidence_id in (
                operand.evidence_identity or operand.evidence_id,
                operand.scale_evidence_identity or operand.scale_evidence_id,
            )
            if evidence_id
        )
    )
    return CalculationExecution(
        status="ok",
        value=result,
        citation_ids=citations,
        step_values=step_values,
    )


def verify_calculation_plan(
    plan: CalculationPlan,
    evidence_items: list[dict[str, Any]],
    *,
    question: str,
    required_slots: list[dict[str, Any]] | None = None,
) -> CalculationVerification:
    errors = _structural_errors(plan, question=question)
    evidence_by_id = calculation_evidence_lookup(evidence_items)
    verified_operands: list[str] = []
    citations: list[str] = []
    for operand in plan.operands:
        operand_errors, operand_citations = _verify_operand(
            operand,
            evidence_by_id,
        )
        errors.extend(operand_errors)
        citations.extend(
            citation for citation in operand_citations if citation not in citations
        )
        if not any(error.endswith(f":{operand.operand_id}") for error in errors):
            verified_operands.append(operand.operand_id)
    errors.extend(_compatibility_errors(plan))
    if plan.answer_scale and plan.answer_unit.lower() not in {"percent", "%", "ratio"}:
        errors.extend(
            f"operand_scale_missing_for_conversion:{operand.operand_id}"
            for operand in plan.operands
            if operand.source == "evidence" and not operand.scale
        )
    (
        required_ids,
        verified_required_ids,
        required_errors,
    ) = verify_required_calculation_slots(
        plan.operands,
        evidence_by_id,
        required_slots or [],
        evidence_text=_evidence_text,
    )
    errors.extend(required_errors)
    return CalculationVerification(
        valid=not errors,
        errors=tuple(dict.fromkeys(errors)),
        verified_operand_ids=tuple(verified_operands),
        citation_ids=tuple(citations),
        required_slot_ids=tuple(required_ids),
        verified_required_slot_ids=tuple(verified_required_ids),
    )


def _verify_operand(
    operand: CalculationOperand,
    evidence_by_id: dict[str, dict[str, Any]],
) -> tuple[list[str], list[str]]:
    lookup_id = operand.evidence_identity or operand.evidence_id
    item = evidence_by_id.get(lookup_id)
    if operand.source != "evidence" or not operand.evidence_id or item is None:
        return [f"operand_evidence_missing:{operand.operand_id}"], []
    errors: list[str] = []
    citations = [lookup_id]
    if (
        operand.evidence_identity
        and calculation_operand_identity(item, operand) != operand.evidence_identity
    ):
        errors.append(f"operand_identity_mismatch:{operand.operand_id}")
    if not operand.cell_id and requires_atomic_calculation_binding(item):
        errors.append(f"operand_atomic_binding_missing:{operand.operand_id}")
    text = _verified_cell_text(operand, item, errors)
    scale_text = text
    if not _value_appears(operand.value, text) and not (
        operand.operand_id.startswith("capital_expenditure")
        and _value_appears(-operand.value, text)
    ):
        errors.append(f"operand_value_mismatch:{operand.operand_id}")
    if _operand_value_is_period(operand):
        errors.append(f"operand_value_is_period:{operand.operand_id}")
    if operand.period and operand.period not in text:
        errors.append(f"operand_period_mismatch:{operand.operand_id}")
    if operand.period_kind and period_kind_conflicts(
        operand.period_kind,
        item,
        _evidence_text(item).lower(),
    ):
        errors.append(f"operand_period_kind_mismatch:{operand.operand_id}")
    if operand.unit and not _term_matches(operand.unit, text):
        errors.append(f"operand_unit_mismatch:{operand.operand_id}")
    if operand.scale_evidence_id:
        scale_lookup_id = operand.scale_evidence_identity or operand.scale_evidence_id
        scale_item = evidence_by_id.get(scale_lookup_id)
        if scale_item is None:
            errors.append(f"operand_scale_evidence_missing:{operand.operand_id}")
        elif not same_source(item, scale_item):
            errors.append(f"operand_scale_source_mismatch:{operand.operand_id}")
        elif not compatible_dimension_scope(item, scale_item):
            errors.append(f"operand_scale_scope_mismatch:{operand.operand_id}")
        else:
            scale_text = _evidence_text(scale_item)
            if (
                operand.scale_evidence_identity
                and identity_of(scale_item).key != operand.scale_evidence_identity
            ):
                errors.append(f"operand_scale_identity_mismatch:{operand.operand_id}")
            citations.append(scale_lookup_id)
    if operand.scale and not _term_matches(operand.scale, scale_text):
        errors.append(f"operand_scale_mismatch:{operand.operand_id}")
    if operand.currency and not _currency_matches(operand.currency, text):
        errors.append(f"operand_currency_mismatch:{operand.operand_id}")
    if operand.entity and not _term_matches(operand.entity, text):
        errors.append(f"operand_entity_mismatch:{operand.operand_id}")
    statement_kind, financial_scope = financial_statement_identity(item)
    if operand.statement_kind and operand.statement_kind != statement_kind:
        errors.append(f"operand_statement_kind_mismatch:{operand.operand_id}")
    if operand.financial_scope and operand.financial_scope != financial_scope:
        errors.append(f"operand_financial_scope_mismatch:{operand.operand_id}")
    return errors, citations


def _verified_cell_text(
    operand: CalculationOperand,
    item: dict[str, Any],
    errors: list[str],
) -> str:
    text = _evidence_text(item)
    if not operand.cell_id:
        return text
    from .financial_table import find_financial_cell_by_id

    cell = find_financial_cell_by_id(item, operand.cell_id)
    if (
        cell is None
        or (
            cell.value != operand.value
            and not (
                operand.operand_id.startswith("capital_expenditure")
                and abs(cell.value) == operand.value
            )
        )
        or (operand.row_label and cell.row_label.lower() != operand.row_label.lower())
        or (
            operand.column_label
            and cell.column_label.lower() != operand.column_label.lower()
        )
    ):
        errors.append(f"operand_cell_mismatch:{operand.operand_id}")
        return text
    return " ".join(
        (
            cell.verification_text(),
            _item_dimension_text(item, "entity"),
        )
    )


def _execute_step(step: CalculationStep, values: list[Decimal]) -> Decimal:
    if step.constant is not None:
        values = [*values, step.constant]
    operator = step.operator
    if operator == "add":
        return sum(values, Decimal("0"))
    if operator == "subtract":
        return values[0] - values[1]
    if operator == "multiply":
        result = Decimal("1")
        for value in values:
            result *= value
        return result
    if operator in {"divide", "ratio"}:
        return values[0] / values[1]
    if operator == "percent_change":
        return (values[1] - values[0]) / abs(values[0]) * Decimal("100")
    if operator == "percentage_of":
        return values[0] / Decimal("100") * values[1]
    if operator == "average":
        return sum(values, Decimal("0")) / Decimal(len(values))
    if operator == "weighted_average":
        midpoint = len(values) // 2
        observations = values[:midpoint]
        weights = values[midpoint:]
        return sum(
            (value * weight for value, weight in zip(observations, weights)),
            Decimal("0"),
        ) / sum(weights, Decimal("0"))
    raise ValueError(operator)


def _operand_value_is_period(operand: CalculationOperand) -> bool:
    match = re.fullmatch(
        r"(?:fy\s*)?((?:19|20)\d{2})",
        str(operand.period or "").strip(),
        flags=re.IGNORECASE,
    )
    return match is not None and operand.value == Decimal(match.group(1))


def _structural_errors(plan: CalculationPlan, *, question: str) -> list[str]:
    errors: list[str] = []
    known_ids = {operand.operand_id for operand in plan.operands}
    if len(known_ids) != len(plan.operands):
        errors.append("duplicate_operand_id")
    for operand in plan.operands:
        if operand.scale.lower() not in _SCALE_FACTORS:
            errors.append(f"unsupported_scale:{operand.operand_id}")
        if operand.source == "question" and str(operand.value) not in question:
            errors.append(f"question_constant_missing:{operand.operand_id}")
    for step in plan.steps:
        if step.operator not in ALLOWED_OPERATORS:
            errors.append(f"unsupported_operator:{step.step_id}")
        for input_id in step.input_ids:
            if input_id not in known_ids:
                errors.append(f"unbound_step_input:{step.step_id}:{input_id}")
        if not _valid_arity(step):
            errors.append(f"invalid_operator_arity:{step.step_id}")
        if step.constant is not None and not _allowed_constant(step, question):
            errors.append(f"unbound_constant:{step.step_id}")
        known_ids.add(step.step_id)
    if plan.result_step_id not in known_ids:
        errors.append("result_step_missing")
    if plan.answer_scale.lower() not in _SCALE_FACTORS:
        errors.append("unsupported_answer_scale")
    return errors


def _valid_arity(step: CalculationStep) -> bool:
    count = len(step.input_ids)
    if step.operator in {
        "subtract",
        "divide",
        "ratio",
        "percent_change",
        "percentage_of",
    }:
        return count == 2
    if step.operator == "weighted_average":
        return count >= 4 and count % 2 == 0
    return count >= 1


def _allowed_constant(step: CalculationStep, question: str) -> bool:
    if step.constant == Decimal("100"):
        return True
    return bool(step.constant_source == "question" and str(step.constant) in question)


def _compatibility_errors(plan: CalculationPlan) -> list[str]:
    operands = {operand.operand_id: operand for operand in plan.operands}
    errors: list[str] = []
    for step in plan.steps:
        direct = [operands[item] for item in step.input_ids if item in operands]
        if len(direct) < 2:
            continue
        if step.operator in {"add", "subtract", "average", "percent_change", "ratio"}:
            for field_name in ("unit", "scale", "currency"):
                values = [
                    str(getattr(operand, field_name) or "").lower()
                    for operand in direct
                ]
                if any(values) and len(set(values)) > 1:
                    errors.append(f"{field_name}_mismatch:{step.step_id}")
    return errors


def _evidence_text(item: dict[str, Any]) -> str:
    metadata = dict(item.get("metadata") or {})
    return " ".join(
        str(value or "")
        for value in (
            item.get("text"),
            item.get("ocr_text"),
            item.get("vlm_text"),
            item.get("caption"),
            metadata.get("table_title"),
            metadata.get("section_title"),
            item.get("unit"),
            metadata.get("unit"),
            item.get("scale"),
            metadata.get("scale"),
            item.get("currency"),
            metadata.get("currency"),
            item.get("period"),
            metadata.get("period"),
            item.get("entity"),
            metadata.get("entity"),
        )
    )


def _item_dimension_text(item: dict[str, Any], field: str) -> str:
    metadata = dict(item.get("metadata") or {})
    return str(item.get(field) or metadata.get(field) or "")


def _value_appears(expected: Decimal, text: str) -> bool:
    return any(value == expected for value in _decimal_values(text))


def _decimal_values(text: str) -> list[Decimal]:
    output: list[Decimal] = []
    for match in _NUMBER_RE.findall(text):
        value = match.replace("$", "").replace(",", "").replace(" ", "")
        negative = "(" in value and value.endswith(")")
        value = value.strip("()")
        try:
            parsed = Decimal(value)
        except InvalidOperation:
            continue
        output.append(-parsed if negative else parsed)
    return output


def _term_matches(term: str, text: str) -> bool:
    return str(term or "").strip().lower() in str(text or "").lower()


def _currency_matches(currency: str, text: str) -> bool:
    normalized = currency.strip().upper()
    aliases = {
        "USD": ("USD", "US$", "$"),
        "EUR": ("EUR", "€"),
        "GBP": ("GBP", "£"),
        "JPY": ("JPY", "¥"),
    }
    return any(
        alias.lower() in text.lower()
        for alias in aliases.get(normalized, (normalized,))
    )


def _scale_factor(scale: str) -> Decimal:
    return _SCALE_FACTORS[str(scale or "").lower()]
