from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field, replace
from typing import Any

QUERY_PLAN_CONTRACT = "query_plan.v1"
MAX_RETRIEVAL_ROUNDS = 2

_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_TOKEN_RE = re.compile(r"[a-z0-9%$€£¥]+", re.IGNORECASE)
_NUMERIC_TERMS = {
    "amount",
    "average",
    "calculate",
    "change",
    "count",
    "difference",
    "margin",
    "percent",
    "percentage",
    "ratio",
    "rate",
    "total",
}
_LONG_FORM_TERMS = {"describe", "explain", "how", "summarize", "why"}
_CROSS_PAGE_TERMS = {"across", "between", "compare", "comparison", "from"}
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


@dataclass(frozen=True)
class EvidenceSlot:
    slot_id: str
    role: str
    entity: str = ""
    metric: str = ""
    period: str = ""
    unit: str = ""
    modality: str = ""
    required: bool = True
    status: str = "missing"
    evidence_ids: tuple[str, ...] = ()
    query: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence_ids"] = list(self.evidence_ids)
        return payload


@dataclass(frozen=True)
class QueryPlan:
    answer_type: str
    question_type: str
    subqueries: tuple[str, ...] = ()
    evidence_slots: tuple[EvidenceSlot, ...] = ()
    constraints: dict[str, Any] = field(default_factory=dict)
    max_retrieval_rounds: int = MAX_RETRIEVAL_ROUNDS
    contract_id: str = QUERY_PLAN_CONTRACT

    def as_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "answer_type": self.answer_type,
            "question_type": self.question_type,
            "subqueries": list(self.subqueries),
            "evidence_slots": [slot.as_dict() for slot in self.evidence_slots],
            "constraints": dict(self.constraints),
            "max_retrieval_rounds": self.max_retrieval_rounds,
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
    normalized_answer_type = _normalized_answer_type(answer_type, tokens)
    periods = list(dict.fromkeys(_YEAR_RE.findall(text)))
    metric = _metric_phrase(tokens, periods)
    question_type = _question_type(tokens, normalized_answer_type, periods)
    slots = _heuristic_slots(
        normalized_answer_type,
        question_type,
        periods,
        metric,
    )
    subqueries = tuple(slot.query for slot in slots if slot.query) or (text,)
    return QueryPlan(
        answer_type=normalized_answer_type,
        question_type=question_type,
        subqueries=subqueries,
        evidence_slots=slots,
        constraints={
            "periods": periods,
            "verification_domain": str(verification_domain or ""),
            "requires_structure": question_type
            in {"cross_page", "multi_period_numeric"},
        },
    )


def bind_evidence_slots(
    plan: QueryPlan,
    evidence_items: list[dict[str, Any]],
) -> QueryPlan:
    bound_slots = []
    for slot in plan.evidence_slots:
        ranked = sorted(
            (
                (score_evidence_for_slot(slot, item), index, item)
                for index, item in enumerate(evidence_items)
            ),
            key=lambda row: (-row[0], row[1]),
        )
        evidence_ids = tuple(
            str(item.get("evidence_id") or item.get("canonical_id") or "")
            for score, _index, item in ranked[:3]
            if score > 0
            and str(item.get("evidence_id") or item.get("canonical_id") or "")
        )
        bound_slots.append(
            replace(
                slot,
                status="filled" if evidence_ids else "missing",
                evidence_ids=evidence_ids,
            )
        )
    return replace(plan, evidence_slots=tuple(bound_slots))


def score_evidence_for_slot(slot: EvidenceSlot, item: dict[str, Any]) -> float:
    text = _evidence_text(item).lower()
    if slot.period and slot.period not in text:
        return 0.0
    modality = str(item.get("modality") or item.get("element_type") or "").lower()
    if slot.modality and slot.modality not in {"auto", modality}:
        return 0.0
    score = 0.0
    metric_tokens = _tokens(slot.metric)
    text_tokens = _tokens(text)
    if metric_tokens:
        score += len(metric_tokens & text_tokens) / len(metric_tokens)
    if slot.period:
        score += 1.0
    if slot.entity and slot.entity.lower() in text:
        score += 0.5
    if slot.unit and slot.unit.lower() in text:
        score += 0.5
    if modality in {"table", "formula"} and slot.role == "operand":
        score += 0.25
    return score


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


def _normalized_answer_type(answer_type: str, tokens: set[str]) -> str:
    value = str(answer_type or "").strip().lower()
    if value in {"numeric", "number", "calculation", "percentage", "ratio"}:
        return "numeric"
    if tokens & _NUMERIC_TERMS:
        return "numeric"
    if value:
        return value
    return "free_text"


def _question_type(tokens: set[str], answer_type: str, periods: list[str]) -> str:
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
