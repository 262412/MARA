from __future__ import annotations

import re

_EXPLICIT_VISUAL_INTENT_RE = re.compile(
    r"\b(?:"
    r"chart|diagram|figure|graph|image|layout|map|photo|photograph|picture|"
    r"plot|screenshot|slide|visual|visible"
    r")\b",
    re.IGNORECASE,
)


def has_explicit_visual_intent(text: str) -> bool:
    """Return whether the question explicitly requires visual interpretation."""

    return bool(_EXPLICIT_VISUAL_INTENT_RE.search(str(text or "")))
