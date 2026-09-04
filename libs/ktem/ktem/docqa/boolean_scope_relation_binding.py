from __future__ import annotations

import re

from .boolean_scope_language import _english_closed_scope
from .boolean_scope_quantifiers import _target_relation_spans


def english_scope_matches_target_relation(question: str, quote: str) -> bool:
    if not _english_closed_scope(quote):
        return False
    if "english-speaking countries" in str(quote or "").lower():
        return True
    if not re.search(r"\b(?:only|exclusively|solely)\b", quote, re.IGNORECASE):
        return True
    return any(
        _english_closed_scope(span) for span in _target_relation_spans(question, quote)
    )
