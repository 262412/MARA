from __future__ import annotations

import re
from typing import Any

from .boolean_proposition_candidates import boolean_proposition_candidate_score
from .boolean_proposition_evidence import boolean_proposition_evidence_score
from .evidence_locators import locator_matches, locator_requirement_count
from .evidence_modality import modality_matches
from .finance_agreement_identity import revolving_agreement_attributes
from .finance_evidence_dimensions import evidence_scale
from .finance_narrative_evidence import finance_narrative_support_quality
from .finance_query_planning import (
    FINANCE_METRIC_ALIASES,
    finance_metric_evidence_matches,
    finance_revenue_row_quality,
)
from .finance_scale import source_scale_evidence
from .financial_statement_identity import matches_required_financial_identity
from .query_evidence_constraints import (
    atomic_evidence,
    executable_operand_evidence,
    period_kind_conflicts,
)
from .query_evidence_text import evidence_text
from .query_plan_schema import EvidenceLocator, EvidenceSlot

_TOKEN_RE = re.compile(r"[a-z0-9%$€£¥]+", re.IGNORECASE)
_MIN_OPERAND_METRIC_COVERAGE = 0.75


def binding_quality(slot: EvidenceSlot, item: dict[str, Any]) -> float:
    quality = 0.0
    if evidence_scale(evidence_text(item), item):
        quality += 1.0
    if str(item.get("materialization_source_id") or "").strip():
        quality += 0.25
    quality += 0.5 * finance_revenue_row_quality(
        slot.metric,
        str(item.get("row_label") or ""),
    )
    return quality


def score_evidence_for_slot(
    slot: EvidenceSlot,
    item: dict[str, Any],
    *,
    requires_structure: bool = False,
) -> float:
    text = " ".join(
        str(value or "")
        for value in (
            evidence_text(item),
            item.get("row_label"),
            item.get("column_label"),
            item.get("period"),
            item.get("value"),
        )
        if str(value or "").strip()
    ).lower()
    locator_score = _locator_score(slot.locator, item)
    if locator_score is None:
        return 0.0
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
    if (
        slot.statement_kind != "boolean_proposition"
        and not matches_required_financial_identity(
            item,
            slot.statement_kind,
            slot.financial_scope,
        )
    ):
        return 0.0
    boolean_score = _boolean_score(slot, item)
    if slot.statement_kind == "boolean_proposition" and boolean_score <= 0:
        return 0.0
    if not _finance_operand_matches(slot, item, text):
        return 0.0
    modality = str(item.get("modality") or item.get("element_type") or "").lower()
    if not modality_matches(slot.modality, modality):
        return 0.0
    return _slot_score(slot, text, modality, locator_score, boolean_score) + (
        finance_narrative_support_quality(slot.metric, item)
        if slot.role == "support"
        else 0.0
    )


def candidate_score_for_slot(
    slot: EvidenceSlot,
    item: dict[str, Any],
    *,
    requires_structure: bool = False,
) -> float:
    """Score retrieval candidates separately from strict authority matching."""

    if slot.statement_kind != "boolean_proposition":
        return score_evidence_for_slot(
            slot,
            item,
            requires_structure=requires_structure,
        )
    text = " ".join(
        str(value or "")
        for value in (
            evidence_text(item),
            item.get("row_label"),
            item.get("column_label"),
            item.get("period"),
            item.get("value"),
        )
        if str(value or "").strip()
    ).lower()
    locator_score = _locator_score(slot.locator, item)
    if locator_score is None:
        return 0.0
    if slot.period and slot.period not in text:
        return 0.0
    if slot.period_kind and period_kind_conflicts(slot.period_kind, item, text):
        return 0.0
    modality = str(item.get("modality") or item.get("element_type") or "").lower()
    if not modality_matches(slot.modality, modality):
        return 0.0
    query = str(slot.query or slot.metric or "").strip()
    return boolean_proposition_candidate_score(
        query,
        item,
        metric=slot.metric,
    )


def agreement_attributes(item: dict[str, Any]) -> dict[str, str]:
    metadata = item.get("metadata")
    nested = metadata if isinstance(metadata, dict) else {}
    observed = revolving_agreement_attributes(evidence_text(item))
    for key in (
        "agreement_lifecycle_status",
        "facility_type",
        "effective_date",
        "facility_identity",
    ):
        value = str(item.get(key) or nested.get(key) or "").strip()
        if value:
            observed[key] = value
    return observed


def trusted_dimension_item(item: dict[str, Any]) -> bool:
    scale, raw_evidence_id = source_scale_evidence(item, [item])
    return bool(scale and item_for_raw_id(raw_evidence_id, [item]) is item)


def item_for_raw_id(
    raw_evidence_id: str,
    evidence_items: list[dict[str, Any]],
) -> dict[str, Any] | None:
    target = str(raw_evidence_id or "").strip()
    if not target:
        return None
    for item in evidence_items:
        aliases = {
            str(item.get(field) or "").strip()
            for field in ("evidence_id", "element_id", "canonical_id", "cell_id")
            if str(item.get(field) or "").strip()
        }
        if target in aliases:
            return item
    return None


def _boolean_score(slot: EvidenceSlot, item: dict[str, Any]) -> float:
    if slot.statement_kind != "boolean_proposition":
        return 0.0
    return boolean_proposition_evidence_score(slot.metric, item)


def _finance_operand_matches(
    slot: EvidenceSlot,
    item: dict[str, Any],
    text: str,
) -> bool:
    if slot.metric not in FINANCE_METRIC_ALIASES:
        return True
    if slot.metric == "revolving credit capacity" and slot.entity.startswith("active"):
        attributes = agreement_attributes(item)
        if attributes["agreement_lifecycle_status"] != "active":
            return False
        as_of_date = slot.entity.removeprefix("active_at:")
        effective_date = attributes["effective_date"]
        if (
            slot.entity.startswith("active_at:")
            and effective_date
            and effective_date > as_of_date
        ):
            return False
    if slot.required_for_execution and not executable_operand_evidence(item):
        return False
    if not atomic_evidence(item):
        return False
    metric_text = " ".join(
        value
        for value in (
            text,
            str(item.get("row_label") or "").lower(),
            str(item.get("caption") or "").lower(),
        )
        if value
    )
    if slot.metric in {"net sales", "revenue"} and not finance_revenue_row_quality(
        slot.metric,
        str(item.get("row_label") or ""),
    ):
        return False
    if not finance_metric_evidence_matches(slot.metric, metric_text):
        return False
    observed_period = str(item.get("period") or item.get("column_label") or "").strip()
    return (not slot.period or observed_period == slot.period) and item.get(
        "value"
    ) not in (None, "")


def _slot_score(
    slot: EvidenceSlot,
    text: str,
    modality: str,
    locator_score: float,
    boolean_score: float,
) -> float:
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
    score = locator_score + boolean_score + metric_coverage
    if slot.modality not in {"", "auto"} and (
        locator_score > 0 or metric_coverage > 0 or slot.modality.lower() == modality
    ):
        score += 0.25
    score += 1.0 if slot.period else 0.0
    score += 0.5 if slot.entity and slot.entity.lower() in text else 0.0
    score += 0.5 if slot.unit and slot.unit.lower() in text else 0.0
    score += (
        0.25 if modality in {"table", "formula"} and slot.role == "operand" else 0.0
    )
    return score


def slot_item_materialized(slot: EvidenceSlot, item: dict[str, Any]) -> bool:
    if slot.role == "dimension":
        return bool(
            item.get("scale")
            or item.get("unit")
            or item.get("text")
            or item.get("ocr_text")
        )
    if slot.required_for_execution:
        if item.get("value") not in (None, ""):
            return True
        return (
            not slot.statement_kind
            and not slot.financial_scope
            and bool(item.get("span_id") or item.get("text") or item.get("ocr_text"))
        )
    return bool(item.get("text") or item.get("ocr_text") or item.get("value"))


def slot_semantic_match(
    slot: EvidenceSlot,
    item: dict[str, Any],
    *,
    requires_structure: bool,
) -> bool:
    if (
        slot.statement_kind == "segment_table"
        and str(item.get("statement_kind") or "") == "segment_table"
        and str(item.get("financial_scope") or "") == "segment"
        and (
            not slot.period
            or str(item.get("period") or item.get("column_label") or "") == slot.period
        )
        and item.get("value") not in (None, "")
    ):
        return True
    return (
        candidate_score_for_slot(slot, item, requires_structure=requires_structure) > 0
    )


def _locator_score(
    locator: EvidenceLocator | None,
    item: dict[str, Any],
) -> float | None:
    if locator is None or not locator.as_dict():
        return 0.0
    if not locator_matches(
        item,
        source_id=locator.source_id,
        page_label=locator.page_label,
        page_labels=locator.page_labels,
        element_id=locator.element_id,
        figure_label=locator.figure_label,
        table_label=locator.table_label,
    ):
        return None
    return float(
        locator_requirement_count(
            source_id=locator.source_id,
            page_label=locator.page_label,
            page_labels=locator.page_labels,
            element_id=locator.element_id,
            figure_label=locator.figure_label,
            table_label=locator.table_label,
        )
    )


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


def _tokens(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(str(text or ""))}
