from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from .finance_evidence_dimensions import evidence_scale, requested_scale
from .finance_query_planning import (
    FINANCE_METRIC_ALIASES,
    finance_fact_specs,
    finance_metric_evidence_matches,
    finance_operand_specs,
    is_finance_segment_comparison,
)
from .financial_statement_identity import (
    matches_required_financial_identity,
    required_financial_identity,
)
from .query_evidence_constraints import (
    atomic_evidence,
    period_kind_conflicts,
    period_kind_in_question,
)
from .query_plan_constraints import query_plan_constraints
from .query_plan_schema import MAX_RETRIEVAL_ROUNDS, EvidenceSlot, QueryPlan

_YEAR_RE = re.compile(r"\b(?:fy\s*)?((?:19|20)\d{2})\b|\bfy\s*(\d{2})\b", re.IGNORECASE)
_VALUE_RE = re.compile(r"(?<![A-Za-z0-9])(?:[$€£¥]\s*)?\(?[+-]?\d[\d,]*(?:\.\d+)?%?\)?")
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
_LONG_FORM_TERMS = {"describe", "explain", "how", "summarize", "why"}
_CAUSAL_TERMS = {
    "cause",
    "caused",
    "causes",
    "driver",
    "drivers",
    "drove",
    "factor",
    "factors",
    "reason",
    "reasons",
    "why",
}
_CROSS_PAGE_TERMS = {"across", "between", "compare", "comparison", "from"}
_MIN_OPERAND_METRIC_COVERAGE = 0.75
_VISUAL_TERMS = {
    "chart",
    "diagram",
    "figure",
    "image",
    "plot",
    "slide",
    "table",
    "visual",
}
_METRIC_STOPWORDS = {
    "a",
    "an",
    "and",
    "did",
    "do",
    "for",
    "from",
    "how",
    "in",
    "is",
    "of",
    "the",
    "to",
    "was",
    "were",
    "what",
    "which",
}


def build_query_plan(
    question: str,
    *,
    answer_type: str = "",
    verification_domain: str = "",
    planner_payload: dict[str, Any] | None = None,
) -> QueryPlan:
    if planner_payload and isinstance(planner_payload.get("evidence_slots"), list):
        return _plan_from_payload(
            question,
            answer_type=answer_type,
            verification_domain=verification_domain,
            payload=planner_payload,
        )
    text = str(question or "").strip()
    tokens = _tokens(text)
    causal_intent = bool(tokens & _CAUSAL_TERMS)
    normalized_answer_type = _normalized_answer_type(
        answer_type,
        tokens,
        causal_intent=causal_intent,
    )
    periods = _periods_in_question(text)
    period_kind = period_kind_in_question(text)
    metric = _metric_phrase(tokens, periods)
    question_type = _question_type(
        tokens,
        normalized_answer_type,
        periods,
        causal_intent=causal_intent,
    )
    finance_domain = "finance" in str(verification_domain or "").lower()
    segment_comparison = finance_domain and is_finance_segment_comparison(text)
    if segment_comparison:
        question_type = "comparison_argmax"
    finance_specs = (
        finance_operand_specs(text, periods)
        if normalized_answer_type == "numeric" and finance_domain
        else ()
    )
    finance_fact = (
        finance_domain and normalized_answer_type != "numeric" and not causal_intent
    )
    finance_support_specs = finance_fact_specs(text, periods) if finance_fact else ()
    slots = (
        _finance_slots(
            finance_specs or finance_support_specs,
            require_scale=bool(finance_specs and requested_scale(text)),
            role="operand" if finance_specs else "support",
            period_kind=period_kind,
        )
        if finance_specs or finance_support_specs
        else _heuristic_slots(
            normalized_answer_type,
            question_type,
            periods,
            metric,
        )
    )
    subqueries = tuple(slot.query for slot in slots if slot.query) or (text,)
    constraints = query_plan_constraints(
        text,
        question_type=question_type,
        periods=periods,
        verification_domain=verification_domain,
        segment_comparison=segment_comparison,
    )
    if segment_comparison:
        slots = _segment_comparison_slots(slots)
        subqueries = tuple(slot.query for slot in slots if slot.query)
    return QueryPlan(
        answer_type=normalized_answer_type,
        question_type=question_type,
        subqueries=subqueries,
        evidence_slots=slots,
        constraints=constraints,
    )


def request_planning_question(request: Any) -> str:
    return str(
        getattr(request, "controller_question", None)
        or getattr(request, "retrieval_query", None)
        or getattr(request, "prompt", "")
        or ""
    ).strip()


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


def bind_evidence_slots(
    plan: QueryPlan,
    evidence_items: list[dict[str, Any]],
) -> QueryPlan:
    bound_slots = []
    used_generic_operand_ids: set[str] = set()
    for slot in plan.evidence_slots:
        ranked = sorted(
            (
                (
                    score_evidence_for_slot(
                        slot,
                        item,
                        requires_structure=bool(
                            plan.constraints.get("requires_structure")
                        ),
                    ),
                    index,
                    item,
                )
                for index, item in enumerate(evidence_items)
            ),
            key=lambda row: (-row[0], row[1]),
        )
        candidate_ids = [
            str(item.get("evidence_id") or item.get("canonical_id") or "")
            for score, _index, item in ranked[:3]
            if score > 0
            and str(item.get("evidence_id") or item.get("canonical_id") or "")
        ]
        if slot.role == "operand" and not slot.period:
            candidate_ids = [
                evidence_id
                for evidence_id in candidate_ids
                if evidence_id not in used_generic_operand_ids
            ][:1]
            used_generic_operand_ids.update(candidate_ids)
        evidence_ids = tuple(candidate_ids)
        bound_slots.append(
            replace(
                slot,
                status="filled" if evidence_ids else "missing",
                evidence_ids=evidence_ids,
            )
        )
    return replace(plan, evidence_slots=tuple(bound_slots))


def score_evidence_for_slot(
    slot: EvidenceSlot,
    item: dict[str, Any],
    *,
    requires_structure: bool = False,
) -> float:
    text = _evidence_text(item).lower()
    if slot.role == "dimension":
        detected_scale = evidence_scale(text, item)
        if not detected_scale or (slot.scale and slot.scale != detected_scale):
            return 0.0
        return 2.0
    if slot.period and slot.period not in text:
        return 0.0
    if slot.period_kind and period_kind_conflicts(slot.period_kind, item, text):
        return 0.0
    if slot.role == "operand" and requires_structure and not atomic_evidence(item):
        return 0.0
    if not matches_required_financial_identity(
        item,
        slot.statement_kind,
        slot.financial_scope,
    ):
        return 0.0
    if slot.metric in FINANCE_METRIC_ALIASES:
        if not atomic_evidence(item):
            return 0.0
        if not finance_metric_evidence_matches(slot.metric, text):
            return 0.0
        if not _bound_numeric_value(slot, item, text):
            return 0.0
    modality = str(item.get("modality") or item.get("element_type") or "").lower()
    if slot.modality and slot.modality not in {"auto", modality}:
        return 0.0
    score = 0.0
    text_tokens = _tokens(text)
    metric_token_sets = [
        _tokens(alias)
        for alias in FINANCE_METRIC_ALIASES.get(slot.metric, (slot.metric,))
        if alias
    ]
    metric_coverage = _metric_coverage(metric_token_sets, text_tokens)
    if (
        slot.role == "operand"
        and slot.metric
        and metric_coverage < _MIN_OPERAND_METRIC_COVERAGE
    ):
        return 0.0
    if metric_token_sets:
        score += metric_coverage
    if slot.period:
        score += 1.0
    if slot.entity and slot.entity.lower() in text:
        score += 0.5
    if slot.unit and slot.unit.lower() in text:
        score += 0.5
    if modality in {"table", "formula"} and slot.role == "operand":
        score += 0.25
    return score


def _metric_coverage(
    metric_token_sets: list[set[str]],
    text_tokens: set[str],
) -> float:
    coverages = [
        len(metric_tokens & text_tokens) / len(metric_tokens)
        for metric_tokens in metric_token_sets
        if metric_tokens
    ]
    return max(coverages, default=0.0)


def _bound_numeric_value(
    slot: EvidenceSlot,
    item: dict[str, Any],
    text: str,
) -> bool:
    evidence_id = str(
        item.get("cell_id")
        or item.get("element_id")
        or item.get("evidence_id")
        or item.get("canonical_id")
        or ""
    ).strip()
    if not evidence_id:
        return False
    if not finance_metric_evidence_matches(slot.metric, text):
        return False
    from .financial_table import parse_financial_table_cells

    cells = parse_financial_table_cells(item)
    if cells:
        aliases = FINANCE_METRIC_ALIASES.get(slot.metric, (slot.metric,))
        return any(
            (not slot.period or cell.period == slot.period)
            and _metric_coverage(
                [_tokens(alias) for alias in aliases if alias],
                _tokens(cell.row_label),
            )
            >= _MIN_OPERAND_METRIC_COVERAGE
            for cell in cells
        )
    values = [match.group(0).strip("() ") for match in _VALUE_RE.finditer(text)]
    if slot.period:
        values = [value for value in values if value != slot.period]
    return bool(values)


def missing_required_slots(plan: QueryPlan) -> list[EvidenceSlot]:
    return [
        slot
        for slot in plan.evidence_slots
        if slot.required and slot.status != "filled"
    ]


def missing_slot_queries(plan: QueryPlan) -> list[str]:
    return list(
        dict.fromkeys(slot.query for slot in missing_required_slots(plan) if slot.query)
    )


def slot_coverage(plan: QueryPlan) -> float | None:
    required = [slot for slot in plan.evidence_slots if slot.required]
    if not required:
        return None
    return sum(slot.status == "filled" for slot in required) / len(required)


def retrieval_budget(plan: QueryPlan) -> dict[str, int]:
    if plan.question_type in {"multi_period_numeric", "numeric", "cross_page"}:
        return {"max_items": 16, "max_pages": 6}
    if plan.question_type == "visual":
        return {"max_items": 8, "max_pages": 6}
    if plan.question_type == "long_form":
        return {"max_items": 12, "max_pages": 5}
    return {"max_items": 8, "max_pages": 3}


def _heuristic_slots(
    answer_type: str,
    question_type: str,
    periods: list[str],
    metric: str,
) -> tuple[EvidenceSlot, ...]:
    if question_type == "multi_period_numeric":
        return tuple(
            EvidenceSlot(
                slot_id=f"operand:{period}",
                role="operand",
                metric=metric,
                period=period,
                modality="auto",
                query=" ".join(value for value in (metric, period) if value),
            )
            for period in periods
        )
    if answer_type == "numeric":
        roles = ("operand:primary", "operand:secondary")
        return tuple(
            EvidenceSlot(
                slot_id=slot_id,
                role="operand",
                metric=metric,
                modality="auto",
                query=metric,
            )
            for slot_id in roles
        )
    if question_type == "cross_page":
        return (
            EvidenceSlot(
                slot_id="support:cross_page",
                role="support",
                metric=metric,
                modality="auto",
                query=metric,
            ),
        )
    return ()


def _finance_slots(
    specs: tuple[tuple[str, str, str], ...],
    *,
    require_scale: bool,
    role: str = "operand",
    period_kind: str = "",
) -> tuple[EvidenceSlot, ...]:
    slots = []
    for slot_id, metric, period in specs:
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
                query=" ".join(value for value in (metric, period) if value),
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
            query="tabular dollars unit scale convention",
        ),
    )


def _periods_in_question(question: str) -> list[str]:
    periods = list(
        dict.fromkeys(
            full or f"20{short}" for full, short in _YEAR_RE.findall(question)
        )
    )
    if len(periods) != 2 or not re.search(
        r"\b(?:from|between)\b.*\b(?:and|through|to)\b",
        question,
        flags=re.IGNORECASE,
    ):
        return periods
    start, end = (int(value) for value in periods)
    if start >= end or end - start > 10:
        return periods
    return [str(year) for year in range(start, end + 1)]


def _normalized_answer_type(
    answer_type: str,
    tokens: set[str],
    *,
    causal_intent: bool = False,
) -> str:
    value = str(answer_type or "").strip().lower()
    if causal_intent:
        return (
            value
            if value and value not in {"numeric", "number", "calculation"}
            else "free_text"
        )
    if value in {"numeric", "number", "calculation", "percentage", "ratio"}:
        return "numeric"
    if tokens & _NUMERIC_TERMS:
        return "numeric"
    if value:
        return value
    return "free_text"


def _question_type(
    tokens: set[str],
    answer_type: str,
    periods: list[str],
    *,
    causal_intent: bool = False,
) -> str:
    if causal_intent:
        return "long_form"
    if answer_type == "numeric" and len(periods) >= 2:
        return "multi_period_numeric"
    if answer_type == "numeric":
        return "numeric"
    if tokens & _VISUAL_TERMS:
        return "visual"
    if tokens & _CROSS_PAGE_TERMS:
        return "cross_page"
    if tokens & _LONG_FORM_TERMS:
        return "long_form"
    return "simple_fact"


def _metric_phrase(tokens: set[str], periods: list[str]) -> str:
    values = [
        token
        for token in tokens
        if token not in _METRIC_STOPWORDS
        and token not in _NUMERIC_TERMS
        and token not in set(periods)
    ]
    return " ".join(sorted(values))


def _plan_from_payload(
    question: str,
    *,
    answer_type: str,
    verification_domain: str,
    payload: dict[str, Any],
) -> QueryPlan:
    slots = tuple(
        EvidenceSlot(
            slot_id=str(item.get("slot_id") or f"slot:{index}"),
            role=str(item.get("role") or "support"),
            entity=str(item.get("entity") or ""),
            metric=str(item.get("metric") or ""),
            period=str(item.get("period") or ""),
            unit=str(item.get("unit") or ""),
            scale=str(item.get("scale") or ""),
            statement_kind=str(item.get("statement_kind") or ""),
            financial_scope=str(item.get("financial_scope") or ""),
            modality=str(item.get("modality") or "auto"),
            required=bool(item.get("required", True)),
            query=str(item.get("query") or "").strip(),
        )
        for index, item in enumerate(payload.get("evidence_slots") or [], start=1)
        if isinstance(item, dict)
    )
    subqueries = tuple(
        str(item).strip()
        for item in payload.get("subqueries") or []
        if str(item).strip()
    )
    return QueryPlan(
        answer_type=str(payload.get("answer_type") or answer_type or "free_text"),
        question_type=str(payload.get("question_type") or "planned"),
        subqueries=subqueries or tuple(slot.query for slot in slots if slot.query),
        evidence_slots=slots,
        constraints={
            **dict(payload.get("constraints") or {}),
            "verification_domain": verification_domain,
            "question": question,
        },
        max_retrieval_rounds=min(
            MAX_RETRIEVAL_ROUNDS,
            max(1, int(payload.get("max_retrieval_rounds") or MAX_RETRIEVAL_ROUNDS)),
        ),
    )


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(str(text or ""))}


def _evidence_text(item: dict[str, Any]) -> str:
    metadata = dict(item.get("metadata") or {})
    return " ".join(
        str(value or "")
        for value in (
            item.get("text"),
            item.get("ocr_text"),
            item.get("vlm_text"),
            item.get("caption"),
            metadata.get("section_title"),
            metadata.get("table_title"),
        )
    )
