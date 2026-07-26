from __future__ import annotations

from collections.abc import Callable

QASPER_VERIFIER_PROMPT_MAX_CHARS = 7000
_TRUNCATION_NOTICE = (
    "\n\n[additional retrieved evidence omitted to fit the verifier prompt budget]"
)


def fit_qasper_verifier_prompt(
    evidence: str,
    prompt_builder: Callable[[str], str],
) -> tuple[str, str, dict[str, str]]:
    original = str(evidence or "")
    full_prompt = prompt_builder(original)
    if len(full_prompt) <= QASPER_VERIFIER_PROMPT_MAX_CHARS:
        return (
            full_prompt,
            original,
            _budget_trace(
                status="full",
                original=original,
                used=original,
                prompt=full_prompt,
            ),
        )

    empty_prompt = prompt_builder("")
    evidence_limit = max(
        0,
        QASPER_VERIFIER_PROMPT_MAX_CHARS - len(empty_prompt) - len(_TRUNCATION_NOTICE),
    )
    bounded = _truncate_evidence(original, evidence_limit)
    if bounded:
        bounded = f"{bounded}{_TRUNCATION_NOTICE}"
    prompt = prompt_builder(bounded)
    if len(prompt) > QASPER_VERIFIER_PROMPT_MAX_CHARS:
        overflow = len(prompt) - QASPER_VERIFIER_PROMPT_MAX_CHARS
        bounded = bounded[:-overflow] if overflow < len(bounded) else ""
        prompt = prompt_builder(bounded)
    return (
        prompt,
        bounded,
        _budget_trace(
            status="truncated",
            original=original,
            used=bounded,
            prompt=prompt,
        ),
    )


def _truncate_evidence(evidence: str, limit: int) -> str:
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


def _budget_trace(
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
        "verifier_prompt_char_limit": str(QASPER_VERIFIER_PROMPT_MAX_CHARS),
    }
