from __future__ import annotations

import re


def answer_claims(answer: str) -> list[str]:
    cleaned = _remove_inner_abstain_text(re.sub(r"<[^>]+>", " ", str(answer or "")))
    claims = []
    for chunk in re.split(r"(?<=[.!?])\s+", cleaned):
        claim = " ".join(chunk.split())
        if claim and not _is_non_factual_claim(claim):
            claims.append(claim)
    return claims


def _remove_inner_abstain_text(answer: str) -> str:
    return str(answer or "").replace("文档证据无法支持该回答。", " ")


def _is_non_factual_claim(claim: str) -> bool:
    lowered = claim.strip().lower()
    if lowered.startswith(
        ("okay,", "first,", "now,", "let's ", "i need to ", "looking at ")
    ):
        return True
    general_explanations = (
        "also known as",
        "calculated as",
        "defined as",
        "different from the current ratio",
        "excludes inventory",
        "measures a company's ability",
    )
    return any(phrase in lowered for phrase in general_explanations)
