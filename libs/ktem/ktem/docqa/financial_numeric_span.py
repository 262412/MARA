from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from .finance_agreement_identity import (
    revolving_agreement_attributes,
    revolving_capacity_amount,
)
from .finance_query_planning import FINANCE_METRIC_ALIASES


@dataclass(frozen=True)
class FinancialNumericFact:
    span_index: int
    clause: str
    metric: str
    value: Decimal
    scale: str
    currency: str
    agreement_attributes: dict[str, str]


def financial_numeric_facts(text: str) -> tuple[FinancialNumericFact, ...]:
    facts: list[FinancialNumericFact] = []
    agreement_context: dict[str, str] = {}
    seen_agreements: set[tuple[str, str, str, str]] = set()
    for span_index, clause in enumerate(_financial_fact_clauses(text), start=1):
        metric = _finance_metric(clause)
        amounts = _financial_amounts(clause)
        agreement_attributes = revolving_agreement_attributes(
            clause,
            default_date=agreement_context.get("effective_date", ""),
            default_facility_type=agreement_context.get("facility_type", ""),
            default_lifecycle_status=agreement_context.get(
                "agreement_lifecycle_status",
                "",
            ),
        )
        if "credit agreement" in clause.lower():
            agreement_context = agreement_attributes
        if metric == "revolving credit capacity":
            capacity_amount = revolving_capacity_amount(clause)
            amounts = (capacity_amount,) if capacity_amount is not None else amounts[:1]
        if not metric or len(amounts) != 1:
            continue
        value, scale, currency = amounts[0]
        agreement_key = (
            agreement_attributes.get("facility_identity", ""),
            agreement_attributes.get("agreement_lifecycle_status", ""),
            str(value),
            scale,
        )
        if metric == "revolving credit capacity" and agreement_key in seen_agreements:
            continue
        if metric == "revolving credit capacity":
            seen_agreements.add(agreement_key)
        facts.append(
            FinancialNumericFact(
                span_index=span_index,
                clause=clause,
                metric=metric,
                value=value,
                scale=scale,
                currency=currency,
                agreement_attributes=agreement_attributes,
            )
        )
    return tuple(facts)


def _financial_fact_clauses(text: str) -> tuple[str, ...]:
    return tuple(
        " ".join(clause.split())
        for paragraph in re.split(r"(?:\r?\n){2,}", str(text or ""))
        for clause in re.split(
            r"(?<=[.!?])\s+(?=[A-Z])|[;]+",
            " ".join(line.strip() for line in paragraph.splitlines()),
        )
        if clause.strip()
    )


def _finance_metric(text: str) -> str:
    normalized = _normalized_words(text)
    if "credit agreement" in normalized and (
        "borrow up to" in normalized
        or bool(re.search(r"\b(?:entered into|terminated)\b", normalized))
    ):
        return "revolving credit capacity"
    for metric, aliases in FINANCE_METRIC_ALIASES.items():
        if any(
            f" {_normalized_words(alias)} " in f" {normalized} " for alias in aliases
        ):
            return metric
    return ""


def _financial_amounts(text: str) -> tuple[tuple[Decimal, str, str], ...]:
    pattern = re.compile(
        r"(?:(?P<currency>[$€£¥])\s*)?"
        r"(?P<value>\(?[+-]?\d[\d,]*(?:\.\d+)?\)?)"
        r"(?:\s*(?P<scale>thousands?|millions?|billions?))?",
        flags=re.IGNORECASE,
    )
    values: list[tuple[Decimal, str, str]] = []
    for match in pattern.finditer(text):
        currency_symbol = str(match.group("currency") or "")
        scale = str(match.group("scale") or "").lower().rstrip("s")
        if not currency_symbol and not scale:
            continue
        value = _decimal_amount(match.group("value"))
        if value is None:
            continue
        currency = {"$": "USD", "€": "EUR", "£": "GBP", "¥": "JPY"}.get(
            currency_symbol,
            "",
        )
        values.append((value, scale, currency))
    return tuple(values)


def _decimal_amount(value: str) -> Decimal | None:
    normalized = str(value or "").replace(",", "").strip()
    negative = normalized.startswith("(") and normalized.endswith(")")
    try:
        parsed = Decimal(normalized.strip("()"))
    except InvalidOperation:
        return None
    return -parsed if negative else parsed


def _normalized_words(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", str(value or "").lower()))
