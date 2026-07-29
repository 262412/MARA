from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

_NUMBER_WORDS = {
    "zero": 0,
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
}
_PRECISION_RE = re.compile(
    r"(?:round(?:ed)?|give|report|to)\D{0,32}"
    r"(?P<places>\d+|zero|one|two|three|four|five|six)"
    r"\s+decimal\s+place",
    re.IGNORECASE,
)


def compare_calculation_result(
    raw_result: Decimal,
    rendered_value: Decimal,
    *,
    prompt: str,
    plan: dict[str, Any],
    rendered_text: str,
) -> dict[str, Any]:
    normalized_result = _normalize_unit(raw_result, plan)
    decimal_places, precision_source = _decimal_places(
        prompt,
        plan,
        rendered_value,
        rendered_text,
    )
    if decimal_places is None:
        quantized_result = normalized_result
        quantized_rendered = rendered_value
    else:
        quantum = Decimal("1").scaleb(-decimal_places)
        quantized_result = normalized_result.quantize(quantum, rounding=ROUND_HALF_UP)
        quantized_rendered = rendered_value.quantize(
            quantum,
            rounding=ROUND_HALF_UP,
        )
    matched = quantized_result == quantized_rendered
    return {
        "raw_calculation_result": str(raw_result),
        "normalized_calculation_result": str(normalized_result),
        "rendered_answer_value": str(rendered_value),
        "answer_unit": str(plan.get("answer_unit") or ""),
        "answer_scale": str(plan.get("answer_scale") or ""),
        "decimal_places": decimal_places,
        "rounding_mode": "ROUND_HALF_UP",
        "precision_source": precision_source,
        "quantized_calculation_result": str(quantized_result),
        "quantized_rendered_answer": str(quantized_rendered),
        "matched": matched,
    }


def _normalize_unit(value: Decimal, plan: dict[str, Any]) -> Decimal:
    answer_unit = str(plan.get("answer_unit") or "").strip().lower()
    result_unit = (
        str(plan.get("raw_result_unit") or plan.get("execution_value_unit") or "")
        .strip()
        .lower()
    )
    if answer_unit in {"percent", "%"} and result_unit in {"fraction", "ratio"}:
        return value * Decimal("100")
    return value


def _decimal_places(
    prompt: str,
    plan: dict[str, Any],
    rendered_value: Decimal,
    rendered_text: str,
) -> tuple[int | None, str]:
    match = _PRECISION_RE.search(str(prompt or ""))
    if match:
        value = match.group("places").lower()
        return int(value) if value.isdigit() else _NUMBER_WORDS[value], "question"
    formula_places = plan.get("rounding_places")
    if formula_places is None:
        result_step_id = str(plan.get("result_step_id") or "")
        formula_places = next(
            (
                step.get("rounding_places")
                for step in plan.get("steps") or []
                if isinstance(step, dict)
                and str(step.get("step_id") or "") == result_step_id
            ),
            None,
        )
    if formula_places is not None:
        try:
            return int(formula_places), "formula_spec"
        except (TypeError, ValueError):
            pass
    answer_contract = plan.get("answer_contract")
    if isinstance(answer_contract, dict):
        contract_places = answer_contract.get("decimal_places")
        if contract_places is not None:
            try:
                return int(contract_places), "answer_contract"
            except (TypeError, ValueError):
                pass
    if "." in format(rendered_value, "f"):
        exponent = rendered_value.as_tuple().exponent
        places = max(0, -exponent) if isinstance(exponent, int) else 0
        return places, "rendered_answer"
    if "." in str(rendered_text or ""):
        return 0, "rendered_answer"
    return None, "exact"
