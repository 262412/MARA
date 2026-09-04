from __future__ import annotations

import hashlib
import re


def content_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(value or "").casefold())
        if len(token) > 3
    }


def truncate_evidence(evidence: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(evidence) <= limit:
        return evidence
    prefix = evidence[:limit].rstrip()
    paragraph_boundary = prefix.rfind("\n\n")
    sentence_boundary = prefix.rfind(". ")
    boundary = max(paragraph_boundary, sentence_boundary)
    if boundary >= limit // 2:
        prefix = prefix[: boundary + (1 if boundary == sentence_boundary else 0)]
    return prefix.rstrip()


def budget_trace(
    *,
    status: str,
    original: str,
    used: str,
    prompt: str,
) -> dict[str, str]:
    return {
        "evidence_budget_status": status,
        "evidence_chars_original": str(len(original)),
        "evidence_chars_used": str(len(used)),
        "verifier_prompt_chars": str(len(prompt)),
        "verifier_prompt_char_limit": "7000",
        "canonical_prompt_fingerprint": hashlib.sha256(
            prompt.encode("utf-8")
        ).hexdigest(),
    }
