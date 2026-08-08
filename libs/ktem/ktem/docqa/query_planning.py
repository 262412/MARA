from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from .finance_agreement_identity import agreement_date
from .finance_evidence_dimensions import requested_scale
from .finance_query_planning import (
    finance_fact_specs,
    finance_formula_spec,
    finance_formula_status,
    finance_operand_specs,
    is_finance_segment_comparison,
)
from .financial_statement_identity import required_financial_identity
from .heuristic_query_slots import heuristic_slots
from .query_classification import (
    has_causal_intent,
    normalized_answer_type,
    question_capabilities,
    question_type,
)
from .query_evidence_binding import bind_evidence_slots as _bind_evidence_slots
from .query_evidence_binding import score_evidence_for_slot as _score_evidence_for_slot
from .query_evidence_constraints import period_kind_in_question
from .query_phrase_extraction import metric_phrase, periods_in_question
from .query_plan_constraints import query_plan_constraints
from .query_plan_schema import (
    EvidenceLocator,
    EvidenceSlot,
    QueryPlan,
    initial_plan_from_payload,
    with_plan_id,
)

_TOKEN_RE = re.compile(r"[a-z0-9%$€£¥]+", re.IGNORECASE)
_NUMERIC_TERMS = {
    "amount",
    "average",
    "calculate",
    "change",
    "count",
    "difference",
    "decline",
    "drop",
    "ebitda",
    "margin",
    "million",
    "millions",
    "billion",
    "billions",
    "percent",
    "percentage",
    "ratio",
    "rate",
    "total",
}


def build_query_plan(
    question: str,
    *,
    answer_type: str = "",
    verification_domain: str = "",
    planner_payload: QueryPlan | dict[str, Any] | None = None,
) -> QueryPlan:
    planned = initial_plan_from_payload(
        question,
        answer_type=answer_type,
        verification_domain=verification_domain,
        payload=planner_payload,
    )
    registry_status = finance_formula_status(question, periods_in_question(question))
    finance_domain = "finance" in str(verification_domain or "").lower()
    if planned is not None and not (
        finance_domain
        and planned.answer_type == "numeric"
        and registry_status in {"supported", "unsupported"}
    ):
        return planned
    return _build_heuristic_query_plan(
        question,
        answer_type=answer_type,
        verification_domain=verification_domain,
    )


def _build_heuristic_query_plan(
    question: str,
    *,
    answer_type: str,
    verification_domain: str,
) -> QueryPlan:
    text = str(question or "").strip()
    tokens = _tokens(text)
    causal_intent = has_causal_intent(tokens)
    normalized_type = normalized_answer_type(
        answer_type,
        tokens,
        question=text,
        numeric_terms=_NUMERIC_TERMS,
        causal_intent=causal_intent,
    )
    periods = periods_in_question(text)
    period_kind = period_kind_in_question(text)
    metric = metric_phrase(text, periods, numeric_terms=_NUMERIC_TERMS)
    capabilities = question_capabilities(text, tokens)
    planned_question_type = question_type(
        tokens,
        normalized_type,
        periods,
        causal_intent=causal_intent,
        requires_multiple_evidence=bool(capabilities["requires_multiple_evidence"]),
    )
    slots, finance_domain, segment_comparison = _heuristic_evidence_slots(
        text,
        normalized_type=normalized_type,
        planned_question_type=planned_question_type,
        periods=periods,
        period_kind=period_kind,
        metric=metric,
        capabilities=capabilities,
        verification_domain=verification_domain,
        causal_intent=causal_intent,
    )
    if segment_comparison:
        planned_question_type = "comparison_argmax"
        slots = _segment_comparison_slots(slots)
    subqueries = tuple(slot.query for slot in slots if slot.query) or (text,)
    constraints = query_plan_constraints(
        text,
        question_type=planned_question_type,
        periods=periods,
        verification_domain=verification_domain,
        segment_comparison=segment_comparison,
        capabilities=capabilities,
    )
    _add_finance_formula_constraint(
        constraints,
        text,
        periods,
        finance_domain and normalized_type == "numeric",
    )
    _add_distinct_slot_constraint(constraints, slots)
    plan = QueryPlan(
        answer_type=normalized_type,
        question_type=planned_question_type,
        subqueries=subqueries,
        evidence_slots=slots,
        constraints=constraints,
    )
    return with_plan_id(plan, text)


def _heuristic_evidence_slots(
    text: str,
    *,
    normalized_type: str,
    planned_question_type: str,
    periods: list[str],
    period_kind: str,
    metric: str,
    capabilities: dict[str, object],
    verification_domain: str,
    causal_intent: bool,
) -> tuple[tuple[EvidenceSlot, ...], bool, bool]:
    inferred_finance_specs = (
        finance_operand_specs(text, periods) if normalized_type == "numeric" else ()
    )
    finance_domain = "finance" in str(verification_domain or "").lower() or bool(
        inferred_finance_specs
    )
    segment_comparison = finance_domain and is_finance_segment_comparison(text)
    finance_specs = inferred_finance_specs if finance_domain else ()
    formula_status = (
        finance_formula_status(text, periods)
        if finance_domain and normalized_type == "numeric"
        else "not_applicable"
    )
    finance_fact = finance_domain and normalized_type != "numeric" and not causal_intent
    finance_support_specs = finance_fact_specs(text, periods) if finance_fact else ()
    slots: tuple[EvidenceSlot, ...] = (
        ()
        if formula_status == "unsupported"
        else _finance_slots(
            finance_specs or finance_support_specs,
            require_scale=bool(finance_specs and requested_scale(text)),
            role="operand" if finance_specs else "support",
            period_kind=period_kind,
            page_labels=_explicit_page_labels(capabilities),
            query_context=text,
        )
        if finance_specs or finance_support_specs
        else heuristic_slots(
            text,
            normalized_type,
            planned_question_type,
            periods,
            metric,
            capabilities,
            verification_domain,
        )
    )
    if "total" in text.lower() and any(
        slot.metric == "revolving credit capacity" for slot in slots
    ):
        active_date = agreement_date(text)
        slots = tuple(
            replace(
                slot,
                cardinality=2,
                operator_role="collection",
                entity=f"active_at:{active_date}" if active_date else "active",
            )
            if slot.metric == "revolving credit capacity"
            else slot
            for slot in slots
        )
    slots = _apply_fiscal_quarter_qualifiers(text, slots)
    return slots, finance_domain, segment_comparison


def _apply_fiscal_quarter_qualifiers(
    question: str,
    slots: tuple[EvidenceSlot, ...],
) -> tuple[EvidenceSlot, ...]:
    qualifiers = {
        match.group("year"): match.group("quarter").lower()
        for match in re.finditer(
            r"\b(?P<quarter>q[1-4])\s+(?:of\s+)?fy\s*(?P<year>(?:19|20)\d{2})\b",
            question,
            flags=re.IGNORECASE,
        )
    }
    if not qualifiers:
        return slots
    return tuple(
        replace(
            slot,
            period_kind="quarter",
            entity=f"fiscal_quarter:{qualifiers[slot.period]}",
        )
        if slot.period in qualifiers
        else slot
        for slot in slots
    )


def _add_finance_formula_constraint(
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


def _add_distinct_slot_constraint(
    constraints: dict[str, Any],
    slots: tuple[EvidenceSlot, ...],
) -> None:
    distinct_slot_ids = tuple(
        slot.slot_id
        for slot in slots
        if slot.slot_id.endswith(("left", "right"))
        or slot.slot_id in {"support:left_subject", "support:right_subject"}
    )
    if distinct_slot_ids:
        constraints["distinct_source_page_slot_ids"] = distinct_slot_ids


def ensure_request_query_plan(
    request: Any,
    *,
    planner_payload: QueryPlan | dict[str, Any] | None = None,
) -> QueryPlan:
    existing = getattr(request, "query_plan", None)
    if isinstance(existing, QueryPlan):
        if not isinstance(getattr(request, "planned_query_plan", None), QueryPlan):
            request.planned_query_plan = existing
        if not getattr(request, "query_plan_id", ""):
            request.query_plan_id = existing.plan_id
        return existing
    payload = existing if isinstance(existing, dict) else planner_payload
    plan = build_query_plan(
        request_planning_question(request),
        answer_type=str(
            getattr(request, "answer_type", None)
            or getattr(request, "task_type", None)
            or ""
        ),
        verification_domain=str(getattr(request, "verification_domain", None) or ""),
        planner_payload=payload,
    )
    request.planned_query_plan = plan
    request.query_plan = plan
    request.query_plan_id = plan.plan_id
    request.query_plan_state_version = 0
    return plan


def request_planning_question(request: Any) -> str:
    return next(
        (
            str(value).strip()
            for value in (
                getattr(request, "controller_question", None),
                getattr(request, "retrieval_query", None),
                getattr(request, "prompt", ""),
            )
            if str(value or "").strip()
        ),
        "",
    )


def bind_evidence_slots(
    plan: QueryPlan,
    evidence_items: list[dict[str, Any]],
) -> QueryPlan:
    return _bind_evidence_slots(plan, evidence_items)


def score_evidence_for_slot(
    slot: EvidenceSlot,
    item: dict[str, Any],
    *,
    requires_structure: bool = False,
) -> float:
    return _score_evidence_for_slot(
        slot,
        item,
        requires_structure=requires_structure,
    )


def _segment_comparison_slots(
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


def missing_required_slots(plan: QueryPlan) -> list[EvidenceSlot]:
    return [
        slot
        for slot in plan.evidence_slots
        if slot.required_for_retrieval and slot.status != "filled"
    ]


def missing_slot_queries(plan: QueryPlan) -> list[str]:
    return list(
        dict.fromkeys(slot.query for slot in missing_required_slots(plan) if slot.query)
    )


def missing_slot_requests(plan: QueryPlan) -> list[dict[str, str]]:
    return [
        {
            "query_id": f"round2:{slot.slot_id}",
            "slot_id": slot.slot_id,
            "query": _second_round_slot_query(slot),
            "modality": slot.modality or "auto",
        }
        for slot in missing_required_slots(plan)
        if slot.query
    ]


def slot_coverage(plan: QueryPlan) -> float | None:
    required = [slot for slot in plan.evidence_slots if slot.required_for_retrieval]
    if not required:
        return None
    return sum(slot.status == "filled" for slot in required) / len(required)


def retrieval_budget(plan: QueryPlan) -> dict[str, int]:
    if plan.question_type in {"multi_period_numeric", "numeric", "cross_page"}:
        required_count = sum(
            slot.required_for_retrieval for slot in plan.evidence_slots
        )
        return {"max_items": max(16, 2 * required_count), "max_pages": 6}
    if plan.question_type == "visual":
        return {"max_items": 8, "max_pages": 6}
    if plan.question_type == "long_form":
        return {"max_items": 12, "max_pages": 5}
    return {"max_items": 8, "max_pages": 3}


def _finance_slots(
    specs: tuple[tuple[str, str, str], ...],
    *,
    require_scale: bool,
    role: str = "operand",
    period_kind: str = "",
    page_labels: tuple[str, ...] = (),
    query_context: str = "",
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
                query=_finance_retrieval_query(
                    metric,
                    period,
                    statement_kind=statement_kind,
                    query_context=query_context,
                ),
                locator=_finance_slot_locator(
                    index,
                    slot_count=len(specs),
                    page_labels=page_labels,
                ),
            )
        )
    slots_tuple = tuple(slots)
    if not require_scale:
        return slots_tuple
    dimension_query = _finance_dimension_query(slots_tuple, query_context)
    return (
        *slots_tuple,
        EvidenceSlot(
            slot_id="dimension:scale",
            role="dimension",
            required_for_execution=True,
            query=dimension_query,
        ),
    )


def _finance_retrieval_query(
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
    if metric == "capital expenditure" and _is_free_cash_flow_query(query_context):
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
    return " ".join(terms)


def _is_free_cash_flow_query(question: str) -> bool:
    lowered = str(question or "").lower()
    return "free cash flow" in lowered or bool(re.search(r"\bfcf\b", lowered))


def _finance_dimension_query(
    slots: tuple[EvidenceSlot, ...],
    query_context: str,
) -> str:
    terms = ["tabular dollars unit scale convention"]
    for slot in slots:
        terms.extend((slot.metric, slot.period, slot.query))
    if _is_free_cash_flow_query(query_context):
        terms.extend(
            (
                "consolidated statement of cash flows",
                "net cash provided by operating activities",
                "purchases of land buildings and equipment",
            )
        )
    return " ".join(dict.fromkeys(term for term in terms if term))


def _second_round_slot_query(slot: EvidenceSlot) -> str:
    if slot.role == "dimension":
        return " ".join(
            dict.fromkeys(
                (
                    slot.query,
                    "parent table dollars scale unit convention",
                    "statement locator",
                )
            )
        )
    expanded = _finance_retrieval_query(
        slot.metric,
        slot.period,
        statement_kind=slot.statement_kind,
        query_context=slot.query,
    )
    identity_terms = [slot.slot_id.replace(":", " "), slot.query, expanded]
    if slot.financial_scope:
        identity_terms.append(slot.financial_scope)
    return " ".join(dict.fromkeys(term for term in identity_terms if term))


def _explicit_page_labels(capabilities: dict[str, object]) -> tuple[str, ...]:
    values = capabilities.get("explicit_page_labels")
    if not isinstance(values, (list, tuple)):
        return ()
    return tuple(str(value).strip() for value in values if str(value).strip())


def _finance_slot_locator(
    index: int,
    *,
    slot_count: int,
    page_labels: tuple[str, ...],
) -> EvidenceLocator:
    if len(page_labels) == slot_count:
        return EvidenceLocator(page_label=page_labels[index])
    return EvidenceLocator(page_labels=page_labels)


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(str(text or ""))}
