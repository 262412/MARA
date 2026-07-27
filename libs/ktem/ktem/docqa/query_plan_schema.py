from __future__ import annotations

from dataclasses import asdict, dataclass, field
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
