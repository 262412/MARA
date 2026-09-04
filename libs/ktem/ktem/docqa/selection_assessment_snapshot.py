from __future__ import annotations

import hashlib
import json
import re
import time
import unicodedata
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from .boolean_proposition_candidates import boolean_proposition_selection_assessment
from .query_evidence_binding_support import candidate_score_for_slot


class SelectionAssessmentCacheMiss(RuntimeError):
    """Raised when selection tries to classify outside its frozen snapshot."""


@dataclass(frozen=True)
class SemanticAssessmentKey:
    frame: str
    slot_role: str
    evidence_identity: str
    content_revision: str


@dataclass(frozen=True)
class SelectionAssessment:
    boolean_score: float
    authority_level: str


@dataclass
class _AssessmentAudit:
    cache_builds: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    classification_calls: int = 0
    mmr_hot_loop_misses: int = 0
    time_spent_ms: float = 0.0


@dataclass(frozen=True)
class SelectionAssessmentSnapshot:
    """Request-local Boolean scores keyed only by semantic inputs."""

    _assessments: Mapping[SemanticAssessmentKey, SelectionAssessment]
    _semantic_candidates: frozenset[tuple[str, str]]
    _slots: frozenset[tuple[str, str]]
    _audit: _AssessmentAudit

    @classmethod
    def build(
        cls,
        plan: Any,
        items: list[dict[str, Any]],
    ) -> SelectionAssessmentSnapshot:
        snapshot = cls(
            MappingProxyType({}),
            frozenset(),
            frozenset(),
            _AssessmentAudit(cache_builds=1),
        )
        return snapshot._expanded(plan, items, initial=True)

    def expanded(
        self,
        plan: Any,
        items: list[dict[str, Any]],
    ) -> SelectionAssessmentSnapshot:
        return self._expanded(plan, items, initial=False)

    def candidate_score(
        self,
        plan: Any,
        slot: Any,
        item: dict[str, Any],
        *,
        hot_loop: bool = False,
    ) -> float:
        if str(slot.statement_kind or "") != "boolean_proposition":
            return candidate_score_for_slot(
                slot,
                item,
                requires_structure=bool(plan.constraints.get("requires_structure")),
            )
        assessment = self._lookup(plan, slot, item, hot_loop=hot_loop)
        return candidate_score_for_slot(
            slot,
            item,
            requires_structure=bool(plan.constraints.get("requires_structure")),
            boolean_assessment_score=assessment.boolean_score,
        )

    def authority_level(
        self,
        plan: Any,
        slot: Any,
        item: dict[str, Any],
    ) -> str:
        return self._lookup(plan, slot, item).authority_level

    def audit(self) -> dict[str, int | float]:
        return {
            "unique_semantic_candidates": len(self._semantic_candidates),
            "slots": len(self._slots),
            "cache_entries": len(self._assessments),
            "cache_builds": self._audit.cache_builds,
            "cache_hits": self._audit.cache_hits,
            "cache_misses": self._audit.cache_misses,
            "classification_calls": self._audit.classification_calls,
            "mmr_hot_loop_misses": self._audit.mmr_hot_loop_misses,
            "time_spent_ms": round(self._audit.time_spent_ms, 3),
        }

    def _lookup(
        self,
        plan: Any,
        slot: Any,
        item: dict[str, Any],
        *,
        hot_loop: bool = False,
    ) -> SelectionAssessment:
        key = semantic_assessment_key(plan, slot, item)
        assessment = self._assessments.get(key)
        if assessment is None:
            self._audit.cache_misses += 1
            if hot_loop:
                self._audit.mmr_hot_loop_misses += 1
            raise SelectionAssessmentCacheMiss(
                "Boolean selection assessment missing for semantic candidate "
                f"{key.evidence_identity}."
            )
        self._audit.cache_hits += 1
        return assessment

    def _expanded(
        self,
        plan: Any,
        items: list[dict[str, Any]],
        *,
        initial: bool,
    ) -> SelectionAssessmentSnapshot:
        slots = [
            slot
            for slot in plan.evidence_slots
            if str(slot.statement_kind or "") == "boolean_proposition"
        ]
        if not slots:
            return self
        missing: dict[SemanticAssessmentKey, tuple[Any, dict[str, Any]]] = {}
        semantic_candidates = set(self._semantic_candidates)
        semantic_slots = set(self._slots)
        canonical_question = str(plan.constraints.get("question") or "").strip()
        for slot in slots:
            slot_key = (
                _frame_revision(slot, canonical_question),
                _normalized_text(slot.role),
            )
            semantic_slots.add(slot_key)
            for item in items:
                key = semantic_assessment_key(plan, slot, item)
                semantic_candidates.add((key.evidence_identity, key.content_revision))
                if key not in self._assessments and key not in missing:
                    missing[key] = (slot, item)
        if not missing:
            if semantic_candidates == set(
                self._semantic_candidates
            ) and semantic_slots == set(self._slots):
                return self
            return SelectionAssessmentSnapshot(
                self._assessments,
                frozenset(semantic_candidates),
                frozenset(semantic_slots),
                self._audit,
            )
        if not initial:
            self._audit.cache_builds += 1
        started = time.perf_counter()
        assessments = dict(self._assessments)
        for key, (slot, item) in missing.items():
            score, authority_level = boolean_proposition_selection_assessment(
                canonical_question or str(slot.query or slot.metric or ""),
                item,
                metric=str(slot.metric or ""),
            )
            self._audit.classification_calls += 1
            assessments[key] = SelectionAssessment(
                boolean_score=score,
                authority_level=authority_level,
            )
        self._audit.time_spent_ms += (time.perf_counter() - started) * 1000
        return SelectionAssessmentSnapshot(
            MappingProxyType(assessments),
            frozenset(semantic_candidates),
            frozenset(semantic_slots),
            self._audit,
        )


def semantic_assessment_key(
    plan: Any,
    slot: Any,
    item: dict[str, Any],
) -> SemanticAssessmentKey:
    canonical_question = str(plan.constraints.get("question") or "").strip()
    return SemanticAssessmentKey(
        frame=_frame_revision(slot, canonical_question),
        slot_role=_normalized_text(slot.role),
        evidence_identity=_semantic_evidence_identity(item),
        content_revision=_fingerprint(_classification_evidence_payload(item)),
    )


def _frame_revision(slot: Any, canonical_question: str = "") -> str:
    return _fingerprint(
        {
            "query": _normalized_text(slot.query),
            "metric": _normalized_text(slot.metric),
            "canonical_question": _normalized_text(canonical_question),
            "statement_kind": _normalized_text(slot.statement_kind),
        }
    )


def _classification_evidence_payload(item: dict[str, Any]) -> dict[str, Any]:
    metadata = item.get("metadata")
    nested = metadata if isinstance(metadata, dict) else {}
    return {
        "text": {
            field: _normalized_text(item.get(field))
            for field in ("text", "ocr_text", "vlm_text", "caption")
        },
        "scope": {
            field: _normalized_text(item.get(field))
            for field in ("section_id", "section_title", "section", "heading")
        },
        "metadata_scope": {
            field: _normalized_text(nested.get(field))
            for field in ("section_id", "section_title", "section", "heading")
        },
    }


def _semantic_evidence_identity(item: dict[str, Any]) -> str:
    metadata = item.get("metadata")
    nested = metadata if isinstance(metadata, dict) else {}

    def value(*fields: str) -> str:
        for field in fields:
            for container in (item, nested):
                raw = container.get(field)
                if raw not in (None, ""):
                    return str(raw).strip()
        return ""

    cell_id = value("cell_id")
    if cell_id:
        return f"cell:{cell_id}"
    span_id = value("span_id")
    if span_id:
        return f"span:{span_id}"
    table_id = value("table_id")
    row_index = value("row_index", "row")
    column_index = value("column_index", "column", "col")
    if table_id and row_index and column_index:
        return f"cell:{table_id}:{row_index}:{column_index}"
    element_id = value("element_id")
    if element_id:
        return f"element:{element_id}"
    evidence_id = value("evidence_id", "doc_id")
    if evidence_id:
        return f"evidence:{evidence_id}"
    normalized_hash = value("normalized_text_hash")
    if normalized_hash:
        return f"text:{normalized_hash}"
    return f"text:{_fingerprint(_classification_evidence_payload(item))}"


def _normalized_text(value: Any) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    lines = [" ".join(line.casefold().split()) for line in normalized.split("\n")]
    text = "\n".join(line for line in lines if line)
    return re.sub(r"\brequirements?\b", "require", text)


def _fingerprint(payload: Any) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
