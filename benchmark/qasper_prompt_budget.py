from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from ktem.docqa.evidence_identity import exact_evidence_aliases, identity_of

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


def fit_qasper_verifier_items(
    evidence_items: list[dict[str, Any]],
    prompt_builder: Callable[[str], str],
    *,
    question: str,
    candidate_answer: str,
    required_evidence_ids: list[str] | None = None,
) -> tuple[str, str, dict[str, str]]:
    required = {
        str(value).strip()
        for value in required_evidence_ids or []
        if str(value).strip()
    }
    records = _ranked_evidence_records(
        evidence_items,
        question=question,
        candidate_answer=candidate_answer,
        required=required,
    )
    empty_prompt = prompt_builder("")
    evidence_limit = max(0, QASPER_VERIFIER_PROMPT_MAX_CHARS - len(empty_prompt))
    selected: list[tuple[str, str]] = []
    dropped: list[str] = []
    used_chars = 0
    for evidence_id, rendered in records:
        separator_chars = 2 if selected else 0
        if used_chars + separator_chars + len(rendered) <= evidence_limit:
            selected.append((evidence_id, rendered))
            used_chars += separator_chars + len(rendered)
        else:
            dropped.append(evidence_id)
    bounded = "\n\n".join(rendered for _evidence_id, rendered in selected)
    prompt = prompt_builder(bounded)
    trace = _budget_trace(
        status="full" if not dropped else "item_packed",
        original="\n\n".join(rendered for _identity, rendered in records),
        used=bounded,
        prompt=prompt,
    )
    trace.update(
        {
            "verifier_input_evidence_ids": ",".join(
                evidence_id for evidence_id, _rendered in selected
            ),
            "verifier_dropped_evidence_ids": ",".join(dropped),
            "verifier_input_character_count": str(len(bounded)),
            "verifier_input_token_count": str(len(re.findall(r"\S+", bounded))),
            "verifier_budget_exhausted": str(bool(dropped)).lower(),
        }
    )
    return prompt, bounded, trace


def _ranked_evidence_records(
    evidence_items: list[dict[str, Any]],
    *,
    question: str,
    candidate_answer: str,
    required: set[str],
) -> list[tuple[str, str]]:
    query_tokens = _content_tokens(f"{question} {candidate_answer}")
    rows: list[tuple[bool, int, int, str, str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(evidence_items):
        text = _item_text(item)
        if not text:
            continue
        try:
            evidence_id = identity_of(item).key
            aliases = exact_evidence_aliases(item)
        except ValueError:
            continue
        if evidence_id in seen:
            continue
        seen.add(evidence_id)
        relevance = len(query_tokens & _content_tokens(text))
        is_required = bool(required & aliases)
        rendered = f"[evidence_id={evidence_id}]\n{text}"
        rows.append((is_required, relevance, index, evidence_id, rendered, text))
    rows.sort(key=lambda row: (-int(row[0]), -row[1], row[2]))
    priority: list[tuple[bool, int, int, str, str, str]] = [
        row for row in rows if row[0]
    ]
    seen_priority = {row[3] for row in priority}
    claim_texts = [
        value.strip()
        for value in re.split(r"(?<=[.!?;])\s+", candidate_answer)
        if value.strip()
    ] or [question]
    for claim in claim_texts:
        claim_tokens = _content_tokens(f"{question} {claim}")
        candidates = [row for row in rows if row[3] not in seen_priority]
        if not candidates:
            break
        best = max(
            candidates,
            key=lambda row: (len(claim_tokens & _content_tokens(row[5])), -row[2]),
        )
        if claim_tokens & _content_tokens(best[5]):
            priority.append(best)
            seen_priority.add(best[3])
    if _looks_boolean(question):
        for negative in (False, True):
            candidate = next(
                (
                    row
                    for row in rows
                    if row[3] not in seen_priority
                    and _has_negation(row[5]) is negative
                    and row[1] > 0
                ),
                None,
            )
            if candidate is not None:
                priority.append(candidate)
                seen_priority.add(candidate[3])
    ordered = [*priority, *(row for row in rows if row[3] not in seen_priority)]
    return [(row[3], row[4]) for row in ordered]


def _content_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", str(value or "").casefold())
        if len(token) > 3
    }


def _item_text(item: dict[str, Any]) -> str:
    return "\n".join(
        str(item.get(field) or "").strip()
        for field in ("text", "ocr_text", "vlm_text", "caption")
        if str(item.get(field) or "").strip()
    )


def _looks_boolean(question: str) -> bool:
    return bool(
        re.match(
            r"^\s*(?:is|are|was|were|do|does|did|can|could|has|have|had|will|would)\b",
            str(question or ""),
            flags=re.IGNORECASE,
        )
    )


def _has_negation(value: str) -> bool:
    return bool(
        re.search(
            r"\b(?:cannot|can't|didn't|doesn't|neither|never|no|not|without)\b",
            str(value or ""),
            flags=re.IGNORECASE,
        )
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
