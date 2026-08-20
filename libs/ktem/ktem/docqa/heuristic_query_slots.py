from __future__ import annotations

import re

from .boolean_evidence_scope import boolean_retrieval_query
from .finance_retrieval_focus import finance_retrieval_query
from .query_evidence_text import requires_multiple_operands
from .query_phrase_extraction import (
    cross_page_support_queries,
    modality_hint,
    semantic_boolean_proposition_metric,
)
from .query_plan_schema import EvidenceLocator, EvidenceSlot

_TREND_TERMS = {
    "change",
    "changed",
    "trend",
    "trended",
    "increase",
    "increased",
    "decrease",
    "decreased",
    "decline",
    "declined",
    "peak",
    "peaked",
    "rise",
    "rose",
    "fall",
    "fell",
}


def heuristic_slots(
    question: str,
    answer_type: str,
    question_type: str,
    periods: list[str],
    metric: str,
    capabilities: dict[str, object],
    verification_domain: str = "",
) -> tuple[EvidenceSlot, ...]:
    multi_evidence = bool(capabilities.get("requires_multiple_evidence"))
    if capabilities.get("requires_visual"):
        return _visual_support_slots(question, metric)
    if question_type == "multi_period_numeric":
        return _period_operand_slots(
            periods,
            metric,
            page_labels=_page_labels(capabilities),
        )
    if answer_type == "numeric" and multi_evidence:
        return _paired_slots(
            question,
            metric,
            role="operand",
            required_for_execution=True,
            page_labels=_page_labels(capabilities),
        )
    if answer_type == "boolean":
        return _boolean_slots(
            question,
            metric,
            multi_evidence=multi_evidence,
            page_labels=_page_labels(capabilities),
            typed_scope="qasper" in verification_domain.lower(),
        )
    if answer_type == "numeric":
        return _numeric_slots(
            question,
            metric,
            page_labels=_page_labels(capabilities),
        )
    if question_type == "cross_page":
        return _paired_slots(
            question,
            metric,
            role="support",
            page_labels=_page_labels(capabilities),
            allow_duplicate_queries=True,
        )
    primary_support = _primary_support_slots(
        question,
        answer_type,
        question_type,
        metric,
        capabilities,
        verification_domain,
    )
    if primary_support:
        return primary_support
    return ()


def visual_time_series_slots(
    periods: list[str],
    metric: str,
) -> tuple[EvidenceSlot, ...]:
    """Require one typed visual cell for every requested period."""

    return tuple(
        EvidenceSlot(
            slot_id=f"support:{period}",
            role="support",
            metric=metric,
            period=period,
            modality="table",
            required_for_execution=False,
            required_for_verification=True,
            statement_kind="visual_time_series_cell",
            query=" ".join(value for value in (metric, period) if value),
            locator=EvidenceLocator(),
        )
        for period in periods
    )


def mmdoc_visual_time_series_slots(
    question: str,
    normalized_type: str,
    periods: list[str],
    metric: str,
    verification_domain: str,
    causal_intent: bool,
) -> tuple[EvidenceSlot, ...]:
    """Plan typed cells only for explicit MMDoc multi-period trend questions."""

    domain = str(verification_domain or "").strip().lower()
    tokens = set(re.findall(r"[a-z0-9]+", str(question or "").lower()))
    if not (
        "mmdoc" in domain
        and normalized_type == "free_text"
        and not causal_intent
        and len(periods) >= 2
        and metric
        and tokens & _TREND_TERMS
    ):
        return ()
    return visual_time_series_slots(periods, metric)


def _visual_support_slots(
    question: str,
    metric: str,
) -> tuple[EvidenceSlot, ...]:
    hinted_modality = modality_hint(question)
    return (
        EvidenceSlot(
            slot_id="support:visual_primary",
            role="support",
            metric=metric or question,
            modality=(
                hinted_modality
                if hinted_modality and hinted_modality != "auto"
                else "page_image"
            ),
            statement_kind="visual_support",
            query=question,
            locator=EvidenceLocator(),
        ),
    )


def _primary_support_slots(
    question: str,
    answer_type: str,
    question_type: str,
    metric: str,
    capabilities: dict[str, object],
    verification_domain: str,
) -> tuple[EvidenceSlot, ...]:
    if "qasper" in verification_domain.lower() and answer_type not in {
        "boolean",
        "formula",
        "numeric",
    }:
        return (
            EvidenceSlot(
                slot_id="support:answer_relation",
                role="support",
                metric=question,
                modality="auto",
                required_for_retrieval=False,
                required_for_verification=True,
                statement_kind="answer_relation",
                query=question,
            ),
        )
    if (
        "finance" not in verification_domain.lower()
        or question_type not in {"simple_fact", "long_form"}
        or answer_type in {"boolean", "formula", "numeric", "unanswerable"}
    ):
        return ()
    page_labels = _page_labels(capabilities)
    return (
        EvidenceSlot(
            slot_id="support:primary",
            role="support",
            metric=metric or question,
            modality="auto",
            query=finance_retrieval_query(question),
            locator=EvidenceLocator(page_label=page_labels[0] if page_labels else ""),
        ),
    )


def _boolean_slots(
    question: str,
    metric: str,
    *,
    multi_evidence: bool,
    page_labels: tuple[str, ...] = (),
    typed_scope: bool = False,
) -> tuple[EvidenceSlot, ...]:
    query = boolean_retrieval_query(question) if typed_scope else question
    statement_kind = "boolean_proposition" if typed_scope else ""
    if not multi_evidence:
        return (
            EvidenceSlot(
                slot_id="support:boolean_proposition",
                role="support",
                metric=semantic_boolean_proposition_metric(question, metric),
                modality="auto",
                required_for_retrieval=not typed_scope,
                required_for_verification=True,
                statement_kind=statement_kind,
                query=query,
                locator=EvidenceLocator(
                    page_label=page_labels[0] if page_labels else ""
                ),
            ),
        )
    paired_slots = _paired_slots(
        question,
        metric,
        role="support",
        page_labels=page_labels,
    )
    if not paired_slots:
        return _boolean_slots(
            question,
            metric,
            multi_evidence=False,
            page_labels=page_labels,
            typed_scope=typed_scope,
        )
    return (
        EvidenceSlot(
            slot_id="support:proposition",
            role="support",
            metric=semantic_boolean_proposition_metric(question, metric),
            modality="auto",
            required_for_retrieval=False,
            statement_kind=statement_kind,
            query=query,
        ),
        *paired_slots,
    )


def _paired_slots(
    question: str,
    metric: str,
    *,
    role: str,
    required_for_execution: bool = False,
    page_labels: tuple[str, ...] = (),
    allow_duplicate_queries: bool = False,
) -> tuple[EvidenceSlot, ...]:
    left_query, right_query = cross_page_support_queries(question, metric)
    if (
        not left_query
        or not right_query
        or (
            not allow_duplicate_queries
            and " ".join(left_query.lower().split())
            == " ".join(right_query.lower().split())
        )
    ):
        return ()
    return tuple(
        EvidenceSlot(
            slot_id=(
                f"{role}:{side}_subject" if role == "support" else f"{role}:{side}"
            ),
            role=role,
            metric=query,
            modality=modality_hint(query),
            required_for_execution=required_for_execution,
            query=query,
            locator=EvidenceLocator(
                page_label=page_labels[index] if index < len(page_labels) else ""
            ),
        )
        for index, (side, query) in enumerate(
            (("left", left_query), ("right", right_query))
        )
    )


def _period_operand_slots(
    periods: list[str],
    metric: str,
    *,
    page_labels: tuple[str, ...] = (),
) -> tuple[EvidenceSlot, ...]:
    return tuple(
        EvidenceSlot(
            slot_id=f"operand:{period}",
            role="operand",
            metric=metric,
            period=period,
            modality="auto",
            required_for_execution=True,
            query=" ".join(value for value in (metric, period) if value),
            locator=EvidenceLocator(
                page_label=page_labels[index] if index < len(page_labels) else ""
            ),
        )
        for index, period in enumerate(periods)
    )


def _numeric_slots(
    question: str,
    metric: str,
    *,
    page_labels: tuple[str, ...] = (),
) -> tuple[EvidenceSlot, ...]:
    slot_ids = (
        ("operand:primary", "operand:secondary")
        if requires_multiple_operands(question)
        else ("operand:primary",)
    )
    return tuple(
        EvidenceSlot(
            slot_id=slot_id,
            role="operand",
            metric=metric,
            modality="auto",
            required_for_execution=True,
            query=metric,
            locator=EvidenceLocator(
                page_label=page_labels[index] if index < len(page_labels) else ""
            ),
        )
        for index, slot_id in enumerate(slot_ids)
    )


def _page_labels(capabilities: dict[str, object]) -> tuple[str, ...]:
    values = capabilities.get("explicit_page_labels")
    if not isinstance(values, (list, tuple)):
        return ()
    return tuple(str(value).strip() for value in values if str(value).strip())
