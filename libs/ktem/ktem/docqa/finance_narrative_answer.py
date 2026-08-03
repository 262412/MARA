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


def _target_year(question: str) -> str:
    match = re.search(r"\bfy\s*((?:19|20)\d{2})\b", question, flags=re.IGNORECASE)
    return match.group(1) if match else ""


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
