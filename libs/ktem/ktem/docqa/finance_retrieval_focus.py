from __future__ import annotations

from dataclasses import replace

from .query_plan_schema import EvidenceSlot, QueryPlan, with_plan_id

_FocusRule = tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]

_FOCUS_RULES: tuple[_FocusRule, ...] = (
    (
        (),
        ("primary customers", "customer base"),
        (
            "limited number of commercial airlines",
            "revenues from a limited number",
            "U.S. government contracts",
            "percent of revenues",
        ),
    ),
    (
        (),
        ("customer concentration", "major customer"),
        (
            "one customer accounted for",
            "consolidated net revenue",
            "year ended",
            "major customer",
        ),
    ),
    (
        (),
        ("retiree", "retirees", "future benefit payments"),
        (
            "Estimated Future Benefit Payments",
            "Pension Benefits",
            "Health Care and Life",
        ),
    ),
    (
        (),
        ("acquisition", "acquisitions", "acquired"),
        (
            "Note Acquisitions",
            "wholly owned subsidiary",
            "acquired all outstanding shares",
        ),
    ),
    (
        (),
        ("what industry", "primarily operate", "industry does"),
        ("Item 1 Business", "company overview", "global leader"),
    ),
    (
        (),
        ("gross margin",),
        ("Total revenues", "Total costs and expenses", "Gross profit"),
    ),
    (
        (),
        ("debt securities", "national securities exchange"),
        ("Section 12(b)", "Section 12(g)", "None"),
    ),
)


def finance_retrieval_focus_terms(question: str) -> tuple[str, ...]:
    normalized = str(question or "").lower()
    terms: list[str] = []
    for required, alternatives, focus in _FOCUS_RULES:
        if all(term in normalized for term in required) and any(
            term in normalized for term in alternatives
        ):
            terms.extend(term for term in focus if term not in terms)
    return tuple(terms)


def finance_retrieval_query(question: str) -> str:
    focus = finance_retrieval_focus_terms(question)
    if not focus:
        return str(question or "")
    return " ".join((str(question or "").strip(), *focus)).strip()


def apply_finance_retrieval_focus(
    plan: QueryPlan,
    question: str,
    *,
    verification_domain: str,
) -> QueryPlan:
    slots = apply_finance_retrieval_focus_to_slots(
        plan.evidence_slots,
        question,
        verification_domain=verification_domain,
    )
    if slots == plan.evidence_slots:
        return plan
    subqueries = tuple(slot.query for slot in slots if slot.query) or plan.subqueries
    focused = replace(plan, evidence_slots=slots, subqueries=subqueries)
    return with_plan_id(focused, question)


def apply_finance_retrieval_focus_to_slots(
    slots: tuple[EvidenceSlot, ...],
    question: str,
    *,
    verification_domain: str,
) -> tuple[EvidenceSlot, ...]:
    if "finance" not in str(verification_domain or "").lower():
        return slots
    focus = finance_retrieval_focus_terms(question)
    if not focus:
        return slots
    return tuple(
        replace(
            slot,
            query=" ".join(
                (slot.query,)
                + tuple(
                    term for term in focus if term.lower() not in slot.query.lower()
                )
            ).strip(),
        )
        if slot.query
        else slot
        for slot in slots
    )
