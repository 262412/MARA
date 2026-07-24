from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from decimal import Decimal, DivisionByZero, InvalidOperation, localcontext
from typing import Any

from .finance_query_planning import FINANCE_METRIC_ALIASES

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
    unit: str = ""
    scale: str = ""
    currency: str = ""
    period: str = ""
    entity: str = ""
    source: str = "evidence"

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["value"] = str(self.value)
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
            operand.evidence_id
            for operand in plan.operands
            if operand.evidence_id and operand.source == "evidence"
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
    evidence_by_id = _evidence_lookup(evidence_items)
    verified_operands: list[str] = []
    citations: list[str] = []
    for operand in plan.operands:
        item = evidence_by_id.get(operand.evidence_id)
        if operand.source != "evidence" or not operand.evidence_id or item is None:
            errors.append(f"operand_evidence_missing:{operand.operand_id}")
            continue
        text = _evidence_text(item)
        if not _value_appears(operand.value, text):
            errors.append(f"operand_value_mismatch:{operand.operand_id}")
        if operand.period and operand.period not in text:
            errors.append(f"operand_period_mismatch:{operand.operand_id}")
        if operand.unit and not _term_matches(operand.unit, text):
            errors.append(f"operand_unit_mismatch:{operand.operand_id}")
        if operand.scale and not _term_matches(operand.scale, text):
            errors.append(f"operand_scale_mismatch:{operand.operand_id}")
        if operand.currency and not _currency_matches(operand.currency, text):
            errors.append(f"operand_currency_mismatch:{operand.operand_id}")
        if operand.entity and not _term_matches(operand.entity, text):
            errors.append(f"operand_entity_mismatch:{operand.operand_id}")
        if not any(error.endswith(f":{operand.operand_id}") for error in errors):
            verified_operands.append(operand.operand_id)
        if operand.evidence_id not in citations:
            citations.append(operand.evidence_id)
    errors.extend(_compatibility_errors(plan))
    required_ids, verified_required_ids, required_errors = _verify_required_slots(
        plan,
        evidence_by_id,
        required_slots or [],
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


def _verify_required_slots(
    plan: CalculationPlan,
    evidence_by_id: dict[str, dict[str, Any]],
    required_slots: list[dict[str, Any]],
) -> tuple[list[str], list[str], list[str]]:
    slots = [
        slot
        for slot in required_slots
        if bool(slot.get("required", True))
        and str(slot.get("role") or "support") == "operand"
    ]
    required_ids = [str(slot.get("slot_id") or "") for slot in slots]
    verified_ids: list[str] = []
    errors: list[str] = []
    used_operands: set[str] = set()
    for slot, slot_id in zip(slots, required_ids):
        if str(slot.get("status") or "") == "missing":
            errors.append(f"required_slot_missing:{slot_id}")
            continue
        operand = next(
            (
                candidate
                for candidate in plan.operands
                if candidate.operand_id not in used_operands
                and _operand_matches_slot(candidate, slot, evidence_by_id)
            ),
            None,
        )
        if operand is None:
            errors.append(f"required_slot_missing:{slot_id}")
            continue
        used_operands.add(operand.operand_id)
        verified_ids.append(slot_id)
    return required_ids, verified_ids, errors


def _operand_matches_slot(
    operand: CalculationOperand,
    slot: dict[str, Any],
    evidence_by_id: dict[str, dict[str, Any]],
) -> bool:
    period = str(slot.get("period") or "").strip()
    if period and operand.period != period:
        return False
    item = evidence_by_id.get(operand.evidence_id)
    if item is None:
        return False
    allowed_ids = [str(value or "").strip() for value in slot.get("evidence_ids") or []]
    if allowed_ids and not any(
        evidence_by_id.get(value) is item for value in allowed_ids
    ):
        return False
    metric = str(slot.get("metric") or "").strip().lower()
    if metric and not _item_supports_metric(item, metric):
        return False
    return True


def _item_supports_metric(item: dict[str, Any], metric: str) -> bool:
    text_tokens = set(re.findall(r"[a-z0-9]+", _evidence_text(item).lower()))
    aliases = FINANCE_METRIC_ALIASES.get(metric, (metric,))
    return any(
        tokens and len(tokens & text_tokens) / len(tokens) >= 0.75
        for alias in aliases
        if (tokens := set(re.findall(r"[a-z0-9]+", alias.lower())))
    )


def _evidence_lookup(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for item in items:
        identifiers = [
            item.get("evidence_id"),
            item.get("canonical_id"),
            item.get("element_id"),
            *(item.get("duplicate_evidence_ids") or []),
        ]
        for identifier in identifiers:
            value = str(identifier or "").strip()
            if value:
                output[value] = item
    return output


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
