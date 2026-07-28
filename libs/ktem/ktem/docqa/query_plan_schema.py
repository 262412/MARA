from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from typing import Any

QUERY_PLAN_CONTRACT = "query_plan.v1"
MAX_RETRIEVAL_ROUNDS = 2


@dataclass(frozen=True)
class EvidenceSlot:
    slot_id: str
    role: str
    entity: str = ""
    metric: str = ""
    period: str = ""
    period_kind: str = ""
    unit: str = ""
    scale: str = ""
    statement_kind: str = ""
    financial_scope: str = ""
    modality: str = ""
    required: bool = True
    required_for_retrieval: bool = True
    required_for_execution: bool = False
    required_for_verification: bool = True
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
    plan_id: str = ""
    subqueries: tuple[str, ...] = ()
    evidence_slots: tuple[EvidenceSlot, ...] = ()
    constraints: dict[str, Any] = field(default_factory=dict)
    max_retrieval_rounds: int = MAX_RETRIEVAL_ROUNDS
    contract_id: str = QUERY_PLAN_CONTRACT

    def as_dict(self) -> dict[str, Any]:
        return {
            "contract_id": self.contract_id,
            "plan_id": self.plan_id,
            "answer_type": self.answer_type,
            "question_type": self.question_type,
            "subqueries": list(self.subqueries),
            "evidence_slots": [slot.as_dict() for slot in self.evidence_slots],
            "constraints": dict(self.constraints),
            "max_retrieval_rounds": self.max_retrieval_rounds,
        }


def plan_from_payload(
    question: str,
    *,
    answer_type: str,
    verification_domain: str,
    payload: dict[str, Any],
) -> QueryPlan:
    slots = tuple(
        _slot_from_payload(index, item)
        for index, item in enumerate(payload.get("evidence_slots") or [], start=1)
        if isinstance(item, dict)
    )
    subqueries = tuple(
        str(item).strip()
        for item in payload.get("subqueries") or []
        if str(item).strip()
    )
    plan = QueryPlan(
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
    return with_plan_id(
        plan,
        question,
        requested_plan_id=str(payload.get("plan_id") or ""),
    )


def initial_plan_from_payload(
    question: str,
    *,
    answer_type: str,
    verification_domain: str,
    payload: QueryPlan | dict[str, Any] | None,
) -> QueryPlan | None:
    if isinstance(payload, QueryPlan):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get("evidence_slots"), list):
        return plan_from_payload(
            question,
            answer_type=answer_type,
            verification_domain=verification_domain,
            payload=payload,
        )
    return None


def with_plan_id(
    plan: QueryPlan,
    question: str,
    *,
    requested_plan_id: str = "",
) -> QueryPlan:
    if requested_plan_id:
        return replace(plan, plan_id=requested_plan_id)
    payload = plan.as_dict()
    payload.pop("plan_id", None)
    payload["question"] = str(question or "").strip()
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
    return replace(plan, plan_id=f"plan:{hashlib.sha256(encoded).hexdigest()[:20]}")


def _slot_from_payload(index: int, item: dict[str, Any]) -> EvidenceSlot:
    role = str(item.get("role") or "support")
    required = bool(item.get("required", True))
    return EvidenceSlot(
        slot_id=str(item.get("slot_id") or f"slot:{index}"),
        role=role,
        entity=str(item.get("entity") or ""),
        metric=str(item.get("metric") or ""),
        period=str(item.get("period") or ""),
        period_kind=str(item.get("period_kind") or ""),
        unit=str(item.get("unit") or ""),
        scale=str(item.get("scale") or ""),
        statement_kind=str(item.get("statement_kind") or ""),
        financial_scope=str(item.get("financial_scope") or ""),
        modality=str(item.get("modality") or "auto"),
        required=required,
        required_for_retrieval=bool(item.get("required_for_retrieval", required)),
        required_for_execution=bool(
            item.get("required_for_execution", role in {"operand", "dimension"})
        ),
        required_for_verification=bool(item.get("required_for_verification", required)),
        status=str(item.get("status") or "missing"),
        evidence_ids=tuple(
            str(value).strip()
            for value in item.get("evidence_ids") or []
            if str(value).strip()
        ),
        query=str(item.get("query") or "").strip(),
    )
