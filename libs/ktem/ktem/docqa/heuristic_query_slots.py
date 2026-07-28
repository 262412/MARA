from __future__ import annotations

from .query_evidence_text import requires_multiple_operands
from .query_phrase_extraction import cross_page_support_queries, modality_hint
from .query_plan_schema import EvidenceLocator, EvidenceSlot


def heuristic_slots(
    question: str,
    answer_type: str,
    question_type: str,
    periods: list[str],
    metric: str,
    capabilities: dict[str, object],
) -> tuple[EvidenceSlot, ...]:
    multi_evidence = bool(capabilities.get("requires_multiple_evidence"))
    if question_type == "multi_period_numeric":
        return _period_operand_slots(periods, metric)
    if answer_type == "numeric" and multi_evidence:
        return _paired_slots(
            question,
            metric,
            role="operand",
            required_for_execution=True,
            page_labels=_page_labels(capabilities),
        )
    if answer_type == "boolean":
        return _boolean_slots(question, metric, multi_evidence=multi_evidence)
    if answer_type == "numeric":
        return _numeric_slots(question, metric)
    if question_type == "cross_page":
        return _paired_slots(
            question,
            metric,
            role="support",
            page_labels=_page_labels(capabilities),
        )
    if capabilities.get("requires_visual"):
        return (
            EvidenceSlot(
                slot_id="support:visual_primary",
                role="support",
                metric=metric,
                modality=modality_hint(question),
                query=question,
                locator=EvidenceLocator(
                    figure_label=str(capabilities.get("figure_label") or ""),
                    table_label=str(capabilities.get("table_label") or ""),
                ),
            ),
        )
    return ()


def _boolean_slots(
    question: str,
    metric: str,
    *,
    multi_evidence: bool,
) -> tuple[EvidenceSlot, ...]:
    if not multi_evidence:
        return (
            EvidenceSlot(
                slot_id="support:boolean_proposition",
                role="support",
                metric=metric,
                modality="auto",
                query=question,
            ),
        )
    return (
        EvidenceSlot(
            slot_id="support:proposition",
            role="support",
            metric=metric,
            modality="auto",
            required_for_retrieval=False,
            query=question,
        ),
        *_paired_slots(question, metric, role="support"),
    )


def _paired_slots(
    question: str,
    metric: str,
    *,
    role: str,
    required_for_execution: bool = False,
    page_labels: tuple[str, ...] = (),
) -> tuple[EvidenceSlot, ...]:
    left_query, right_query = cross_page_support_queries(question, metric)
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
        )
        for period in periods
    )


def _numeric_slots(
    question: str,
    metric: str,
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
        )
        for slot_id in slot_ids
    )


def _page_labels(capabilities: dict[str, object]) -> tuple[str, ...]:
    values = capabilities.get("explicit_page_labels")
    if not isinstance(values, (list, tuple)):
        return ()
    return tuple(str(value).strip() for value in values if str(value).strip())
