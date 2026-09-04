from __future__ import annotations

import re
import unicodedata

_WHITESPACE_RE = re.compile(r"\s+", re.UNICODE)


def normalize_evidence_label(value: object) -> str:
    normalized = unicodedata.normalize("NFKC", str(value or ""))
    return _WHITESPACE_RE.sub(" ", normalized).strip()
