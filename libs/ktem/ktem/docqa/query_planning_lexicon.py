from __future__ import annotations

import re

NUMERIC_TERMS = {
    "amount",
    "average",
    "calculate",
    "change",
    "count",
    "difference",
    "decline",
    "drop",
    "ebitda",
    "margin",
    "million",
    "millions",
    "billion",
    "billions",
    "percent",
    "percentage",
    "ratio",
    "rate",
    "total",
}

_TOKEN_RE = re.compile(r"[a-z0-9%$€£¥]+", re.IGNORECASE)


def planning_tokens(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(str(text or ""))}
