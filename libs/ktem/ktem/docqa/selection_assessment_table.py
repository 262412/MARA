from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from .evidence_identity import identity_of
from .finance_query_planning import finance_metric_evidence_matches
from .query_evidence_binding_support import candidate_score_for_slot
from .query_plan_schema import QueryPlan


@dataclass(frozen=True)
class SelectionAssessment:
    candidate_score: float
    selection_score: float


@dataclass(frozen=True)
class _SelectionAssessmentKey:
    frame: str
    evidence_identity: str
    content_revision: str


@dataclass(frozen=True)
class SelectionAssessmentTable:
    """Immutable scores for one request-local candidate snapshot."""

    _assessments: Mapping[_SelectionAssessmentKey, SelectionAssessment]

    @classmethod
    def build(
        cls,
        plan: QueryPlan,
        items: list[dict[str, Any]],
    ) -> SelectionAssessmentTable:
        assessments: dict[_SelectionAssessmentKey, SelectionAssessment] = {}
        for slot in plan.evidence_slots:
            for item in items:
                key = _assessment_key(plan, slot, item)
                if key in assessments:
                    continue
                candidate_score = candidate_score_for_slot(
                    slot,
                    item,
                    requires_structure=bool(plan.constraints.get("requires_structure")),
                )
                assessments[key] = SelectionAssessment(
                    candidate_score=candidate_score,
                    selection_score=_selection_score(
                        plan,
                        slot,
                        item,
                        candidate_score,
                    ),
                )
        return cls(MappingProxyType(assessments))

    def get(
        self,
        plan: QueryPlan,
        slot: Any,
        item: dict[str, Any],
    ) -> SelectionAssessment | None:
        return self._assessments.get(_assessment_key(plan, slot, item))


def candidate_assessment_score(
    plan: QueryPlan,
    slot: Any,
    item: dict[str, Any],
    assessments: SelectionAssessmentTable | None = None,
) -> float:
    cached = assessments.get(plan, slot, item) if assessments is not None else None
    if cached is not None:
        return cached.candidate_score
    return candidate_score_for_slot(
        slot,
        item,
        requires_structure=bool(plan.constraints.get("requires_structure")),
    )


def selection_assessment_score(
    plan: QueryPlan,
    slot: Any,
    item: dict[str, Any],
    assessments: SelectionAssessmentTable | None = None,
) -> float:
    cached = assessments.get(plan, slot, item) if assessments is not None else None
    if cached is not None:
        return cached.selection_score
    candidate_score = candidate_score_for_slot(
        slot,
        item,
        requires_structure=bool(plan.constraints.get("requires_structure")),
    )
    return _selection_score(plan, slot, item, candidate_score)


def _selection_score(
    plan: QueryPlan,
    slot: Any,
    item: dict[str, Any],
    candidate_score: float,
) -> float:
    if candidate_score > 0 or not (
        slot.required_for_execution and slot.role == "operand"
    ):
        return candidate_score
    if _is_atomic_operand_candidate(item):
        return 0.0
    text = " ".join(
        str(item.get(field) or "")
        for field in ("text", "caption", "ocr_text", "table_title")
    ).lower()
    metric = str(slot.metric or "").strip().lower()
    table_like = bool(
        item.get("table_id")
        or item.get("table_instance_id")
        or str(item.get("modality") or "").lower() == "table"
        or str(item.get("element_type") or "").lower() == "table"
    )
    if table_like and metric and finance_metric_evidence_matches(metric, text):
        return 0.25
    return 0.0


def _is_atomic_operand_candidate(item: dict[str, Any]) -> bool:
    return identity_of(item).kind in {"cell", "span"} and item.get("value") not in (
        None,
        "",
    )


def _assessment_key(
    plan: QueryPlan,
    slot: Any,
    item: dict[str, Any],
) -> _SelectionAssessmentKey:
    return _SelectionAssessmentKey(
        frame=_frame_revision(plan, slot),
        evidence_identity=identity_of(item).key,
        content_revision=_content_revision(item),
    )


def _frame_revision(plan: QueryPlan, slot: Any) -> str:
    slot_payload = slot.as_dict() if hasattr(slot, "as_dict") else vars(slot)
    payload = {
        key: value
        for key, value in slot_payload.items()
        if key not in {"evidence_ids", "status"}
    }
    payload["requires_structure"] = bool(plan.constraints.get("requires_structure"))
    return _fingerprint(_normalized_payload(payload))


_VOLATILE_ITEM_FIELDS = {
    "_selection_relevance_score",
    "_selection_relevance_sources",
    "element_retriever_score",
    "evidence_confidence",
    "hybrid_fusion_components",
    "hybrid_fusion_score",
    "learned_score",
    "reranker_backend",
    "reranker_input_identity",
    "reranker_model",
    "reranker_rank",
    "reranker_score",
    "reranking_score",
    "retrieval_lineage",
    "retriever_score",
    "score",
    "visual_retriever_score",
}


def _content_revision(item: dict[str, Any]) -> str:
    payload = {
        key: value
        for key, value in item.items()
        if key not in _VOLATILE_ITEM_FIELDS and not key.startswith("_selection_")
    }
    return _fingerprint(_normalized_payload(payload))


def _normalized_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): _normalized_payload(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if str(key) not in _VOLATILE_ITEM_FIELDS
            and not str(key).startswith("_selection_")
        }
    if isinstance(value, (list, tuple)):
        return [_normalized_payload(item) for item in value]
    if isinstance(value, set):
        return sorted(_normalized_payload(item) for item in value)
    if isinstance(value, str):
        return " ".join(value.casefold().split())
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)


def _fingerprint(payload: Any) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
