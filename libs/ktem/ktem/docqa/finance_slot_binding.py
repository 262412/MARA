from __future__ import annotations

import re
from typing import Any


def slot_for_formula_input(
    input_id: str,
    execution_slots: list[dict[str, Any]],
    *,
    question_type: str,
) -> dict[str, Any] | None:
    normalized = str(input_id or "").strip().lower()
    aliases = _semantic_input_aliases(normalized, question_type)
    matches = [
        slot
        for slot in execution_slots
        if _slot_matches_input(_slot_input_id(slot), aliases)
    ]
    return matches[0] if len(matches) == 1 else None


def _slot_input_id(slot: dict[str, Any]) -> str:
    slot_id = str(slot.get("slot_id") or "")
    return slot_id.removeprefix("operand:").replace(":", "_").lower()


def _slot_matches_input(slot_input_id: str, aliases: set[str]) -> bool:
    return any(
        slot_input_id == alias
        or bool(re.fullmatch(rf"{re.escape(alias)}_(?:19|20)\d{{2}}", slot_input_id))
        for alias in aliases
    )


def _semantic_input_aliases(input_id: str, question_type: str) -> set[str]:
    formula_aliases = {
        "working_capital": {
            "left": "current_assets",
            "right": "current_liabilities",
        },
        "current_ratio": {
            "numerator": "current_assets",
            "denominator": "current_liabilities",
        },
        "debt_to_equity": {
            "numerator": "total_debt",
            "denominator": "shareholders_equity",
        },
        "gross_margin": {
            "numerator": "gross_profit",
            "denominator": "net_sales",
        },
        "operating_margin": {
            "numerator": "operating_income",
            "denominator": "net_sales",
        },
    }
    semantic = formula_aliases.get(question_type, {}).get(input_id)
    return {input_id, semantic} if semantic else {input_id}
