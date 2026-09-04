from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any

from .evidence_identity import identity_of
from .evidence_text import evidence_text
from .finance_evidence_dimensions import evidence_scale


@dataclass(frozen=True)
class FinanceGrossMarginProfileAnswer:
    answer: str
    current_period: str
    prior_period: str
    current_gross_profit: str
    prior_gross_profit: str
    current_margin: str
    prior_margin: str
    citation_ids: tuple[str, ...]
    cell_ids: tuple[str, ...]
    scale: str
    audit_status: str = "passed"
    contract_id: str = "finance_gross_margin_profile.v1"

    def as_trace(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["citation_ids"] = list(self.citation_ids)
        payload["cell_ids"] = list(self.cell_ids)
        return payload


def finance_gross_margin_profile_answer(
    question: str,
    evidence_items: list[dict[str, Any]],
) -> FinanceGrossMarginProfileAnswer | None:
    lowered = str(question or "").lower()
    if "gross margin" not in lowered or not _has_any(
        lowered, ("improving", "improved", "improve")
    ):
        return None
    target = _target_period(lowered)
    if not target:
        return None
    candidates = []
    for item in evidence_items:
        parsed = _profile_from_item(item, target)
        if parsed is not None:
            candidates.append(parsed)
    if len(candidates) != 1:
        return None
    return candidates[0]


def _profile_from_item(
    item: dict[str, Any],
    target: str,
) -> FinanceGrossMarginProfileAnswer | None:
    text = evidence_text([item])
    normalized = " ".join(text.split())
    if not (
        "consolidated statements of operations" in normalized.lower()
        and "total revenues" in normalized.lower()
        and "total costs and expenses" in normalized.lower()
    ):
        return None
    periods = tuple(dict.fromkeys(re.findall(r"\b(?:19|20)\d{2}\b", normalized)))
    if target not in periods:
        return None
    target_index = periods.index(target)
    if target_index + 1 >= len(periods):
        return None
    prior = periods[target_index + 1]
    revenues = _row_values(normalized, "Total revenues", len(periods))
    costs = _row_values(normalized, "Total costs and expenses", len(periods))
    gross = _row_values(normalized, "Gross profit", len(periods))
    if revenues is None or costs is None:
        return None
    gross = gross or tuple(
        revenue - abs(cost) for revenue, cost in zip(revenues, costs)
    )
    current_revenue = revenues[target_index]
    prior_revenue = revenues[target_index + 1]
    current_gross = gross[target_index]
    prior_gross = gross[target_index + 1]
    if current_revenue <= 0 or prior_revenue <= 0:
        return None
    current_margin = current_gross / current_revenue * Decimal("100")
    prior_margin = prior_gross / prior_revenue * Decimal("100")
    scale = evidence_scale(text, item)
    if not scale:
        return None
    improving = current_margin > prior_margin and current_gross > prior_gross
    answer = (
        f"{'Yes' if improving else 'No'}. Gross profit "
        f"{'improved' if improving else 'changed'} from "
        f"${_amount(prior_gross)} {scale} in FY{prior} to "
        f"${_amount(current_gross)} {scale} in FY{target}. Gross margin "
        f"{'improved' if improving else 'changed'} from {_percent(prior_margin)}% "
        f"in FY{prior} to {_percent(current_margin)}% in FY{target}."
    )
    identity = identity_of(item).key
    citation_id = str(
        item.get("evidence_id") or item.get("canonical_id") or identity
    ).strip()
    return FinanceGrossMarginProfileAnswer(
        answer=answer,
        current_period=target,
        prior_period=prior,
        current_gross_profit=str(current_gross),
        prior_gross_profit=str(prior_gross),
        current_margin=str(current_margin),
        prior_margin=str(prior_margin),
        citation_ids=(citation_id,),
        cell_ids=(
            f"{identity}:row:total-revenues:period:{target}",
            f"{identity}:row:total-revenues:period:{prior}",
            f"{identity}:row:gross-profit:period:{target}",
            f"{identity}:row:gross-profit:period:{prior}",
        ),
        scale=scale,
    )


def _row_values(
    text: str,
    label: str,
    count: int,
) -> tuple[Decimal, ...] | None:
    match = re.search(
        rf"\b{re.escape(label)}\b(?P<values>.*?)(?=[A-Za-z][A-Za-z /()'-]+\s+[$(\d]|$)",
        text,
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    values = []
    for raw in re.findall(r"\(?-?\$?\s*\d[\d,]*(?:\.\d+)?\)?", match.group("values")):
        value = _decimal(raw)
        if value is not None:
            values.append(value)
        if len(values) == count:
            break
    return tuple(values) if len(values) == count else None


def _decimal(value: str) -> Decimal | None:
    text = str(value or "").replace("$", "").replace(",", "").strip()
    negative = text.startswith("(") and text.endswith(")")
    try:
        parsed = Decimal(text.strip("() "))
    except InvalidOperation:
        return None
    return -parsed if negative else parsed


def _target_period(question: str) -> str:
    match = re.search(r"\bfy\s*((?:19|20)\d{2}|\d{2})\b", question)
    if match is None:
        return ""
    value = match.group(1)
    return value if len(value) == 4 else f"20{value}"


def _amount(value: Decimal) -> str:
    return f"{value:,.0f}"


def _percent(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.1"), rounding=ROUND_HALF_UP))


def _has_any(value: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in value for phrase in phrases)
