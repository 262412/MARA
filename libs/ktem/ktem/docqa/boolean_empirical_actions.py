from __future__ import annotations

import re

_EMPIRICAL_ACTION_RE = re.compile(
    r"\b(?:experiment\w*|evaluat\w*|"
    r"test(?:s|ed|ing)?\b(?![\s-]+(?:time|set|data|split|phase|mode)\b)|"
    r"benchmark\w*|"
    r"assess\w*|measur\w*|compar\w*|appl(?:y|ied|ies|ying)|"
    r"(?:demonstrate|demonstrates|demonstrated|demonstrating)\s+"
    r"(?:the\s+)?performance)\b",
    flags=re.IGNORECASE,
)


def empirical_action_present(value: str) -> bool:
    return _EMPIRICAL_ACTION_RE.search(str(value or "")) is not None
