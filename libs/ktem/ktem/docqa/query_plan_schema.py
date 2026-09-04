from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from typing import Any, Callable

from .evidence_identity import evidence_aliases, identity_of
from .finance_agreement_identity import revolving_agreement_attributes

QUERY_PLAN_CONTRACT = "query_plan.v1"
MAX_RETRIEVAL_ROUNDS = 2
EVIDENCE_REFERENCE_BOUND_STATUSES = frozenset(
    {"filled", "verified_support", "verified_conflict"}
)


def required_slot_count(slot: Any) -> int:
    """Return the minimum number of distinct evidence identities for a slot."""

    try:
        return max(1, int(_slot_value(slot, "cardinality") or 1))
    except (TypeError, ValueError):
        return 1


def slot_binding_state(
    slot: Any,
    evidence_items: list[dict[str, Any]] | None = None,
    *,
    semantic_match: Callable[[dict[str, Any]], bool] | None = None,
    materialized: Callable[[dict[str, Any]], bool] | None = None,
    provenance_complete: Callable[[dict[str, Any]], bool] | None = None,
) -> str:
    """Classify a slot from one cardinality-aware binding contract.

    A slot is ``filled`` only when enough canonical identities are present,
    collection facilities are distinct, and every resolved item satisfies the
    semantic, provenance, and materialization checks supplied by the caller.
    Missing or partial collections remain ``retrieved_partial`` so downstream
    recovery cannot mistake one result for a complete collection.
    """

    evidence_ids = _unique_strings(_slot_value(slot, "evidence_ids") or ())
    required = required_slot_count(slot)
    if not evidence_ids:
        return "missing"
    if evidence_items is None:
        if len(evidence_ids) < required:
            return "retrieved_partial"
        return (
            "filled"
            if str(_slot_value(slot, "status") or "")
            in EVIDENCE_REFERENCE_BOUND_STATUSES
            else "retrieved_partial"
        )

    resolved = _resolve_slot_items(evidence_ids, evidence_items)
    canonical_ids = {_canonical_item_id(item) for item in resolved}
    if len(canonical_ids) < required:
        return "retrieved_partial"
    if len(resolved) < len(evidence_ids):
        return "retrieved_partial"
    if _collection_facilities_required(slot, resolved):
        facilities = {_facility_identity(item) for item in resolved}
        if "" in facilities or len(facilities) < required:
            return "retrieved_partial"
    if semantic_match is not None and any(
        not semantic_match(item) for item in resolved
    ):
        return "retrieved_partial"
    if provenance_complete is not None and any(
        not provenance_complete(item) for item in resolved
    ):
        return "retrieved_partial"
    if materialized is not None and any(not materialized(item) for item in resolved):
        return "retrieved_partial"
    return "filled"


def _slot_value(slot: Any, key: str) -> Any:
    return slot.get(key) if isinstance(slot, dict) else getattr(slot, key, None)


def _unique_strings(values: Any) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values or ():
        normalized = str(value or "").strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            output.append(normalized)
    return output


def _resolve_slot_items(
    evidence_ids: list[str],
    evidence_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    seen: set[str] = set()
    for evidence_id in evidence_ids:
        item = None
        for candidate in evidence_items:
            if evidence_id == str(candidate.get("canonical_id") or "").strip():
                item = candidate
                break
            try:
                if evidence_id in evidence_aliases(candidate):
                    item = candidate
                    break
            except ValueError:
                continue
        if item is None:
            continue
        identity = _canonical_item_id(item)
        if identity not in seen:
            seen.add(identity)
            resolved.append(item)
    return resolved


def _canonical_item_id(item: dict[str, Any]) -> str:
    return str(item.get("canonical_id") or identity_of(item).key).strip()


def _collection_facilities_required(
    slot: Any,
    items: list[dict[str, Any]],
) -> bool:
    if required_slot_count(slot) <= 1:
        return False
    if str(_slot_value(slot, "operator_role") or "").lower() != "collection":
        return False
    return str(_slot_value(slot, "role") or "") == "operand" and any(
        _facility_identity(item) for item in items
    )


def _facility_identity(item: dict[str, Any]) -> str:
    metadata = item.get("metadata")
    nested = metadata if isinstance(metadata, dict) else {}
    for key in ("facility_identity", "facility_id"):
        value = str(item.get(key) or nested.get(key) or "").strip()
        if value:
            return value
    observed = revolving_agreement_attributes(
        str(item.get("text") or item.get("ocr_text") or item.get("caption") or "")
    )
    parsed = str(observed.get("facility_identity") or "").strip()
    if parsed:
        return parsed
    facility_type = str(
        item.get("facility_type") or nested.get("facility_type") or ""
    ).strip()
    effective_date = str(
        item.get("effective_date") or nested.get("effective_date") or ""
    ).strip()
    return ":".join(value for value in (facility_type, effective_date) if value)


@dataclass(frozen=True)
class EvidenceLocator:
    source_id: str = ""
    page_label: str = ""
    page_labels: tuple[str, ...] = ()
    element_id: str = ""
    figure_label: str = ""
    table_label: str = ""

    def as_dict(self) -> dict[str, Any]:
        payload = {
            key: value
            for key, value in asdict(self).items()
            if str(value or "").strip()
        }
        if self.page_labels:
            payload["page_labels"] = list(self.page_labels)
        return payload


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
    cardinality: int = 1
    operator_role: str = ""
    query: str = ""
    locator: EvidenceLocator | None = None

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["evidence_ids"] = list(self.evidence_ids)
        payload["locator"] = self.locator.as_dict() if self.locator else None
        return payload


def evidence_slot_references_are_bound(
    slot: EvidenceSlot,
    evidence_items: list[dict[str, Any]] | None = None,
) -> bool:
    """Return whether a slot has a complete, cardinality-aware binding."""

    if evidence_items is not None:
        return slot_binding_state(slot, evidence_items) == "filled"
    return str(slot.status or "") in EVIDENCE_REFERENCE_BOUND_STATUSES and len(
        _unique_strings(slot.evidence_ids)
    ) >= required_slot_count(slot)


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
    locator_payload = item.get("locator")
    locator = (
        EvidenceLocator(
            source_id=str(locator_payload.get("source_id") or "").strip(),
            page_label=str(locator_payload.get("page_label") or "").strip(),
            page_labels=tuple(
                str(value).strip()
                for value in locator_payload.get("page_labels") or []
                if str(value).strip()
            ),
            element_id=str(locator_payload.get("element_id") or "").strip(),
            figure_label=str(locator_payload.get("figure_label") or "").strip(),
            table_label=str(locator_payload.get("table_label") or "").strip(),
        )
        if isinstance(locator_payload, dict)
        else None
    )
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
        cardinality=max(1, int(item.get("cardinality") or 1)),
        operator_role=str(item.get("operator_role") or ""),
        query=str(item.get("query") or "").strip(),
        locator=locator,
    )
