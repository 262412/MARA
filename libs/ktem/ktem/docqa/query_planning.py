from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

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
        finance_domain and registry_status in {"supported", "unsupported"}
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
    _add_finance_formula_constraint(constraints, text, periods, finance_domain)
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
        slots = tuple(
            replace(slot, cardinality=2, operator_role="collection")
            if slot.metric == "revolving credit capacity"
            else slot
            for slot in slots
        )
    return slots, finance_domain, segment_comparison


def _add_finance_formula_constraint(
    constraints: dict[str, Any],
    question: str,
    periods: list[str],
    finance_domain: bool,
) -> None:
    formula_spec = finance_formula_spec(question, periods) if finance_domain else None
    constraints["finance_formula_status"] = (
        finance_formula_status(question, periods)
        if finance_domain
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
            "query": slot.query,
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
                query=" ".join(value for value in (metric, period) if value),
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
    return (
        *slots_tuple,
        EvidenceSlot(
            slot_id="dimension:scale",
            role="dimension",
            required_for_execution=True,
            query="tabular dollars unit scale convention",
        ),
    )


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
