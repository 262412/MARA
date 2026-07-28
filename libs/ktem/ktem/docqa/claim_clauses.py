from __future__ import annotations

import re

_CLAUSE_BOUNDARY_RE = re.compile(
    r"\s*;\s*|,\s*(?:and|but|while|whereas)\s+|\s+(?:while|whereas)\s+",
    flags=re.IGNORECASE,
)


def split_claim_clauses(claims: list[str]) -> list[str]:
    return [
        clause
        for claim in claims
        for clause in split_claim_text(claim)
        if clause
    ]


def split_claim_text(value: str) -> list[str]:
    return [
        clause.strip()
        for clause in _CLAUSE_BOUNDARY_RE.split(str(value or ""))
        if clause.strip()
    ]
