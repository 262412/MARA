"""Financial contributions to query plans, independent of the plan orchestrator.

Metric and formula recognition remain in finance_query_planning. None means
that generic slot construction should run; an empty tuple is an authoritative
empty result, including unsupported formulas.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any, Callable

from .finance_agreement_identity import agreement_date
from .finance_evidence_dimensions import requested_scale
from .finance_query_planning import (
    finance_fact_specs,
    finance_formula_spec,
    finance_formula_status,
    finance_operand_specs,
    is_finance_segment_comparison,
)
from .finance_retrieval_focus import (
    finance_comparison_operands_required,
    finance_retrieval_focus_terms,
    with_finance_retrieval_focus,
)
from .financial_statement_identity import required_financial_identity
from .query_plan_schema import EvidenceLocator, EvidenceSlot


def is_free_cash_flow_query(question: str) -> bool:
    lowered = str(question or "").lower()
    return "free cash flow" in lowered or bool(re.search(r"\bfcf\b", lowered))


def finance_retrieval_query(
    metric: str,
    period: str,
    *,
    statement_kind: str,
    query_context: str = "",
) -> str:
    terms = [metric]
    aliases = {
        "capital expenditure": ("capital spending",),
        "cost of goods sold": (
            "cost of products sold",
            "cost of revenues",
            "cost of sales",
            "COGS",
        ),
        "operating cash flow": (
            "cash from operations",
            "net cash provided by operating activities",
        ),
        "revolving credit capacity": (
            "revolving credit agreement",
            "revolving credit agreements",
            "borrow up to",
        ),
    }
    terms.extend(aliases.get(metric, ()))
    if metric == "capital expenditure" and is_free_cash_flow_query(query_context):
        terms.extend(("capex", "purchases of land buildings and equipment"))
    headings = {
        "balance_sheet": "consolidated balance sheet",
        "cash_flow_statement": "consolidated statement of cash flows",
        "income_statement": "consolidated statements of income",
        "non_gaap_performance": "non-GAAP reconciliation",
    }
    if statement_kind in headings:
        terms.append(headings[statement_kind])
    if period:
        terms.append(period)
    terms.extend(
        term
        for term in finance_retrieval_focus_terms(query_context)
        if term not in terms
    )
    return " ".join(terms)


def finance_dimension_query(
    slots: tuple[EvidenceSlot, ...],
    query_context: str,
) -> str:
    terms = ["tabular dollars unit scale convention"]
    for slot in slots:
        terms.extend((slot.metric, slot.period, slot.query))
    if is_free_cash_flow_query(query_context):
        terms.extend(
            (
                "consolidated statement of cash flows",
                "net cash provided by operating activities",
                "purchases of land buildings and equipment",
            )
        )
    return " ".join(dict.fromkeys(term for term in terms if term))


def explicit_page_labels(capabilities: dict[str, object]) -> tuple[str, ...]:
    values = capabilities.get("explicit_page_labels")
    if not isinstance(values, (list, tuple)):
        return ()
    return tuple(str(value).strip() for value in values if str(value).strip())


def finance_slot_locator(
    index: int,
    *,
    slot_count: int,
    page_labels: tuple[str, ...],
) -> EvidenceLocator:
    if len(page_labels) == slot_count:
        return EvidenceLocator(page_label=page_labels[index])
    return EvidenceLocator(page_labels=page_labels)


def finance_slots(
    specs: tuple[tuple[str, str, str], ...],
    *,
    require_scale: bool,
    role: str = "operand",
    period_kind: str = "",
    page_labels: tuple[str, ...] = (),
    query_context: str = "",
    retrieval_query: Callable[..., str] = finance_retrieval_query,
    dimension_query: Callable[..., str] = finance_dimension_query,
    slot_locator: Callable[..., EvidenceLocator] = finance_slot_locator,
) -> tuple[EvidenceSlot, ...]:
    slots = []
    for index, (slot_id, metric, period) in enumerate(specs):
        statement_kind, financial_scope = required_financial_identity(metric)
        slots.append(
            EvidenceSlot(
                slot_id=f"operand:{slot_id}",
                role=role,
                metric=metric,
                period=period,
                period_kind=period_kind,
                modality="auto",
                statement_kind=statement_kind,
                financial_scope=financial_scope,
                required_for_execution=role == "operand",
                query=retrieval_query(
                    metric,
                    period,
                    statement_kind=statement_kind,
                    query_context=query_context,
                ),
                locator=slot_locator(
                    index,
                    slot_count=len(specs),
                    page_labels=page_labels,
                ),
            )
        )
    slots_tuple = tuple(slots)
    if not require_scale:
        return slots_tuple
    scale_query = dimension_query(slots_tuple, query_context)
    return (
        *slots_tuple,
        EvidenceSlot(
            slot_id="dimension:scale",
            role="dimension",
            required_for_execution=True,
            query=scale_query,
        ),
    )


def finance_evidence_slots(
    text: str,
    *,
    normalized_type: str,
    periods: list[str],
    period_kind: str,
    capabilities: dict[str, object],
    verification_domain: str,
    causal_intent: bool,
    build_slots: Callable[..., tuple[EvidenceSlot, ...]] = finance_slots,
) -> tuple[tuple[EvidenceSlot, ...] | None, bool, bool]:
    finance_domain_requested = "finance" in str(verification_domain or "").lower()
    inferred_finance_specs = (
        finance_operand_specs(text, periods)
        if normalized_type == "numeric"
        or finance_comparison_operands_required(text, periods, verification_domain)
        else ()
    )
    finance_domain = finance_domain_requested or bool(inferred_finance_specs)
    segment_comparison = finance_domain and is_finance_segment_comparison(text)
    finance_specs = inferred_finance_specs if finance_domain else ()
    formula_status = (
        finance_formula_status(text, periods)
        if finance_domain and normalized_type == "numeric"
        else "not_applicable"
    )
    finance_fact = finance_domain and normalized_type != "numeric" and not causal_intent
    finance_support_specs = finance_fact_specs(text, periods) if finance_fact else ()
    slots = (
        ()
        if formula_status == "unsupported"
        else (
            build_slots(
                finance_specs or finance_support_specs,
                require_scale=bool(finance_specs and requested_scale(text)),
                role="operand" if finance_specs else "support",
                period_kind=period_kind,
                page_labels=explicit_page_labels(capabilities),
                query_context=text,
            )
            if finance_specs or finance_support_specs
            else None
        )
    )
    return slots, finance_domain, segment_comparison


def finalize_finance_slots(
    text: str,
    slots: tuple[EvidenceSlot, ...],
    *,
    finance_domain: bool,
) -> tuple[EvidenceSlot, ...]:
    if "total" in text.lower() and any(
        slot.metric == "revolving credit capacity" for slot in slots
    ):
        active_date = agreement_date(text)
        slots = tuple(
            (
                replace(
                    slot,
                    cardinality=2,
                    operator_role="collection",
                    entity=f"active_at:{active_date}" if active_date else "active",
                )
                if slot.metric == "revolving credit capacity"
                else slot
            )
            for slot in slots
        )
    if finance_domain:
        slots = with_finance_retrieval_focus(slots, text)
    return slots


def segment_comparison_slots(
    slots: tuple[EvidenceSlot, ...],
) -> tuple[EvidenceSlot, ...]:
    return tuple(
        replace(
            slot,
            statement_kind="segment_table",
            financial_scope="segment",
            query=f"reporting segment net revenue {slot.period}".strip(),
        )
        for slot in slots
    )


def add_finance_formula_constraint(
    constraints: dict[str, Any],
    question: str,
    periods: list[str],
    calculation_authoritative: bool,
) -> None:
    formula_spec = (
        finance_formula_spec(question, periods) if calculation_authoritative else None
    )
    constraints["finance_formula_status"] = (
        finance_formula_status(question, periods)
        if calculation_authoritative
        else "not_applicable"
    )
    if formula_spec is not None:
        constraints["finance_formula"] = formula_spec
