from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

_DATE_RE = re.compile(
    r"\b(?:as\s+of\s+|on\s+)?"
    r"(?P<month>january|february|march|april|may|june|july|august|"
    r"september|october|november|december)\s+"
    r"(?P<day>\d{1,2}),?\s+(?P<year>\d{4})\b",
    flags=re.IGNORECASE,
)


def agreement_date(text: str, *, default: str = "") -> str:
    match = _DATE_RE.search(str(text or ""))
    if match is None:
        return default
    parsed = datetime.strptime(
        f"{match.group('month')} {match.group('day')} {match.group('year')}",
        "%B %d %Y",
    )
    return parsed.strftime("%Y-%m-%d")


def revolving_agreement_attributes(
    text: str,
    *,
    default_date: str = "",
    default_facility_type: str = "",
    default_lifecycle_status: str = "",
) -> dict[str, str]:
    lowered = " ".join(str(text or "").lower().split())
    facility_type = default_facility_type
    facility_matches = [
        (match.start(), kind)
        for pattern, kind in (
            (r"\b364[ -]day\b", "364_day"),
            (r"\b(?:five|5)[ -]year\b", "five_year"),
        )
        for match in re.finditer(pattern, lowered)
    ]
    if facility_matches:
        facility_type = max(facility_matches)[1]

    active_index = max(
        (
            lowered.rfind(marker)
            for marker in ("entered into", "entered a new", "new revolving")
        ),
        default=-1,
    )
    inactive_index = max(
        (lowered.rfind(marker) for marker in ("terminated", "expired")),
        default=-1,
    )
    lifecycle_status = default_lifecycle_status
    if active_index >= 0 or inactive_index >= 0:
        lifecycle_status = "active" if active_index > inactive_index else "terminated"
    elif any(marker in lowered for marker in ("currently", "outstanding", "enables")):
        lifecycle_status = "active"

    effective_date = agreement_date(lowered, default=default_date)
    facility_identity = ":".join(
        value for value in (facility_type, effective_date) if value
    )
    return {
        "agreement_lifecycle_status": lifecycle_status,
        "facility_type": facility_type,
        "effective_date": effective_date,
        "facility_identity": facility_identity,
    }


def revolving_capacity_amount(text: str) -> tuple[Decimal, str, str] | None:
    match = re.search(
        r"\bborrow(?:ing)?\s+up\s+to\s+"
        r"(?P<currency>[$€£¥]?)\s*"
        r"(?P<value>\(?[+-]?\d[\d,]*(?:\.\d+)?\)?)"
        r"(?:\s*(?P<scale>thousands?|millions?|billions?))?",
        str(text or ""),
        flags=re.IGNORECASE,
    )
    if match is None:
        return None
    raw_value = match.group("value").replace(",", "")
    negative = raw_value.startswith("(") and raw_value.endswith(")")
    try:
        value = Decimal(raw_value.strip("()"))
    except InvalidOperation:
        return None
    currency = {
        "$": "USD",
        "€": "EUR",
        "£": "GBP",
        "¥": "JPY",
    }.get(match.group("currency"), "")
    scale = str(match.group("scale") or "").lower().rstrip("s")
    if not currency and not scale:
        return None
    return (-value if negative else value), scale, currency
