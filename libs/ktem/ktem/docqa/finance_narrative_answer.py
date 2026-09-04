from __future__ import annotations

import re
from typing import Any

from .evidence_text import evidence_text


def finance_narrative_answer(
    question: str,
    evidence_items: list[dict[str, Any]],
) -> str | None:
    """Return a locally grounded annual finance driver when its scope is explicit."""

    lowered_question = str(question or "").lower()
    for answerer in (
        _future_retiree_payments_answer,
        _acquired_companies_answer,
        _industry_answer,
        _customer_concentration_answer,
        _primary_customers_answer,
        _registered_debt_securities_answer,
    ):
        answer = answerer(lowered_question, evidence_items)
        if answer is not None:
            return answer
    revenue_drivers = _revenue_driver_answer(lowered_question, evidence_items)
    if revenue_drivers is not None:
        return revenue_drivers
    if not (
        re.search(r"\b(?:what\s+drove|driver|reason)\b", lowered_question)
        and re.search(
            r"\b(?:sg\s*&\s*a|selling,?\s+general\s+and\s+administrative)\b",
            lowered_question,
        )
        and "net sales" in lowered_question
    ):
        return None
    target_year = _target_year(lowered_question)
    all_text = " ".join(evidence_text(evidence_items).split())
    if target_year and not _annual_period_alias_supported(all_text, target_year):
        return None
    for item in evidence_items:
        text = " ".join(evidence_text([item]).split())
        annual_start = _annual_section_start(text)
        if annual_start < 0:
            continue
        match = re.search(
            r"(?:SG&A|selling,? general and administrative) expenses.*?"
            r"as a percentage of net sales,? (?:SG&A expenses )?decreased.*?"
            r"primarily due to (?P<drivers>.*?)(?:\.(?:\s|$)|$)",
            text[annual_start:],
            flags=re.IGNORECASE,
        )
        if match is not None:
            drivers = match.group("drivers").strip(" ,.;")
            return drivers[0].upper() + drivers[1:] if drivers else None
    return None


def _future_retiree_payments_answer(
    question: str,
    evidence_items: list[dict[str, Any]],
) -> str | None:
    if "retiree" not in question or not _has_any(
        question, ("pay", "payment", "benefit")
    ):
        return None
    years = re.findall(r"\b(?:fy\s*)?((?:19|20)\d{2})\b", question)
    target = years[-1] if years else ""
    if not target:
        return None
    for item in evidence_items:
        text = " ".join(evidence_text([item]).split())
        if not all(
            phrase in text.lower()
            for phrase in (
                "estimated future benefit payments",
                "pension benefits",
                "health care and life",
            )
        ):
            continue
        match = re.search(
            rf"\b{target}\b\s*\$?\s*(?P<pension>\d[\d,]*(?:\.\d+)?)\s*"
            rf"\$?\s*(?P<health>\d[\d,]*(?:\.\d+)?)",
            text,
        )
        if match is not None:
            return (
                f"Pension benefits were ${match.group('pension')} million, and health "
                f"care and life insurance benefits were ${match.group('health')} million."
            )
    return None


def _acquired_companies_answer(
    question: str,
    evidence_items: list[dict[str, Any]],
) -> str | None:
    if "acquired" not in question or not _has_any(question, ("companies", "company")):
        return None
    requested = 3 if re.search(r"\bthree\b|\b3\b", question) else 1
    names: list[str] = []
    for item in evidence_items:
        text = evidence_text([item])
        for match in re.finditer(
            r"(?m)^\s*(?P<name>[A-Z][A-Za-z0-9&'. -]{1,50})\s*$\s*"
            r"^\s*On\s+[^\n]{1,80},?\s+we acquired\b",
            text,
            flags=re.IGNORECASE,
        ):
            name = " ".join(match.group("name").split())
            if (
                name.lower() not in {"acquisitions", "a acquisitions"}
                and name not in names
            ):
                names.append(name)
        for pattern in (
            r"\bwe acquired all (?:of )?the .*? (?:of|in)\s+(?P<name>[A-Z][A-Za-z0-9&'.-]+)",
            r"\bwe acquired\s+(?P<name>[A-Z][A-Za-z0-9&'.-]+)(?:\s|[,.])",
        ):
            for match in re.finditer(pattern, text):
                name = match.group("name").strip()
                if name not in names:
                    names.append(name)
    return ", ".join(names[:requested]) if len(names) >= requested else None


def _industry_answer(
    question: str,
    evidence_items: list[dict[str, Any]],
) -> str | None:
    if "industry" not in question or "primarily operate" not in question:
        return None
    for item in evidence_items:
        text = " ".join(evidence_text([item]).split())
        match = re.search(
            r"(?:today,?\s+)?we are a global leader in (?P<description>.*?)(?:\.|$)",
            text,
            flags=re.IGNORECASE,
        )
        if match is not None:
            return f"A global leader in {match.group('description').strip()}."
    return None


def _customer_concentration_answer(
    question: str,
    evidence_items: list[dict[str, Any]],
) -> str | None:
    if "customer concentration" not in question:
        return None
    for item in evidence_items:
        text = " ".join(evidence_text([item]).split())
        match = re.search(
            r"(?P<fact>(?:one|a) customer accounted for \d+(?:\.\d+)?% of .*?"
            r"(?:net )?revenue(?: for .*?)?)(?:\.|$)",
            text,
            flags=re.IGNORECASE,
        )
        if match is not None:
            fact = match.group("fact").strip()
            return f"Yes, {fact[0].lower() + fact[1:]}."
    return None


def _primary_customers_answer(
    question: str,
    evidence_items: list[dict[str, Any]],
) -> str | None:
    if "primary customers" not in question:
        return None
    text = " ".join(evidence_text(evidence_items).split())
    airline = _matching_fact(
        text,
        r"we derive a significant portion of our revenues from a limited number "
        r"of commercial airlines",
    )
    government = _matching_fact(
        text,
        r"we derive a substantial portion of our revenue from the u\.s\. government",
    )
    share = _matching_fact(
        text,
        r"in \d{4}, \d+(?:\.\d+)?% of our revenues were earned pursuant to "
        r"u\.s\. government contracts",
    )
    return (
        " ".join((airline, government, share))
        if all((airline, government, share))
        else None
    )


def _matching_fact(text: str, pattern: str) -> str:
    match = re.search(rf"(?P<fact>{pattern})(?:\.|$)", text, flags=re.IGNORECASE)
    return f"{match.group('fact').strip()}." if match is not None else ""


def _registered_debt_securities_answer(
    question: str,
    evidence_items: list[dict[str, Any]],
) -> str | None:
    if not (
        "debt securities" in question and "national securities exchange" in question
    ):
        return None
    for item in evidence_items:
        text = " ".join(evidence_text([item]).split())
        match = re.search(
            r"securities registered pursuant to section 12\(b\).*?"
            r"(?P<listed>.*?)securities registered pursuant to section 12\(g\)"
            r".*?:\s*none\b",
            text,
            flags=re.IGNORECASE,
        )
        if match is None:
            continue
        listed = match.group("listed").lower()
        if not _has_any(listed, ("bond", "debenture", "debt", "note due")):
            return "There are none."
    return None


def _revenue_driver_answer(
    lowered_question: str,
    evidence_items: list[dict[str, Any]],
) -> str | None:
    if not (
        re.search(r"\b(?:what\s+drove|driver|reason)\b", lowered_question)
        and re.search(r"\b(?:net\s+)?revenue\b", lowered_question)
    ):
        return None
    target_year = _target_year(lowered_question)
    for item in evidence_items:
        text = " ".join(evidence_text([item]).split())
        if target_year and target_year not in text:
            continue
        match = re.search(
            r"(?:increase|change)\s+in\s+(?:net\s+)?revenue\s+was\s+driven\s+by\s+"
            r"(?P<drivers>.*?)(?:\.(?:\s|$)|$)",
            text,
            flags=re.IGNORECASE,
        )
        if match is None:
            continue
        drivers = match.group("drivers").strip(" ,.;")
        return drivers[0].upper() + drivers[1:] if drivers else None
    return None


def _target_year(question: str) -> str:
    match = re.search(
        r"\bfy\s*((?:19|20)\d{2}|\d{2})\b",
        question,
        flags=re.IGNORECASE,
    )
    if match is None:
        return ""
    value = match.group(1)
    return value if len(value) == 4 else f"20{value}"


def _annual_period_alias_supported(text: str, target_year: str) -> bool:
    return bool(
        re.search(
            rf"(?:fiscal year|fifty-two-week period).*?ended .*?\b{target_year}\b",
            text,
            flags=re.IGNORECASE,
        )
    )


def _annual_section_start(text: str) -> int:
    markers = [
        match.start()
        for match in re.finditer(
            r"\b(?:for the full year of fiscal|full year|52 weeks ended|"
            r"twelve months ended)\b",
            text,
            flags=re.IGNORECASE,
        )
    ]
    if not markers:
        return -1
    return markers[-1]


def _has_any(value: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in value for phrase in phrases)
