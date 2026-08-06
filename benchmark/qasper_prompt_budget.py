from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from ktem.docqa.evidence_identity import exact_evidence_aliases, identity_of

from .metrics import is_abstention_answer
from .qasper_boolean import stemmed_content_tokens
from .qasper_evidence_identity import canonical_evidence_sort_key, canonical_prompt_span

QASPER_VERIFIER_PROMPT_MAX_CHARS = 7000


@dataclass(frozen=True)
class _EvidenceRow:
    identity: str
    aliases: frozenset[str]
    item: dict[str, Any]
    stable_key: tuple[str, int, int, str]
    canonical_alias: str
    rendered: str
    text: str
    source_text: str
    span_texts: tuple[str, ...]
    index: int
    relevance: int
    required: bool
    claim_support: bool
    claim_contradiction: bool
    priority: bool
    spans: tuple[tuple[int, int], ...]


def compact_qasper_candidate(candidate: str, *, max_chars: int = 1800) -> str:
    """Keep candidate rationale useful without allowing it to consume evidence budget."""

    return _truncate_evidence(str(candidate or ""), max_chars)


def fit_qasper_verifier_items(
    evidence_items: list[dict[str, Any]],
    prompt_builder: Callable[[str], str],
    *,
    question: str,
    candidate_answer: str,
    required_evidence_ids: list[str] | None = None,
    required_slot_ids: list[str] | None = None,
    priority_evidence_ids: list[str] | None = None,
    claim_support_evidence_ids: list[str] | None = None,
    claim_contradiction_evidence_ids: list[str] | None = None,
) -> tuple[str, str, dict[str, str]]:
    required = _normalized_ids(required_evidence_ids)
    records = _ranked_evidence_records(
        evidence_items,
        question=question,
        candidate_answer=candidate_answer,
        required=required,
        priority=_normalized_ids(priority_evidence_ids),
        claim_support=_normalized_ids(claim_support_evidence_ids),
        claim_contradiction=_normalized_ids(claim_contradiction_evidence_ids),
    )
    empty_prompt = prompt_builder("")
    evidence_limit = max(0, QASPER_VERIFIER_PROMPT_MAX_CHARS - len(empty_prompt))
    original_records = list(records)
    records = _reserve_required_record_budget(records, evidence_limit)
    selected: list[_EvidenceRow] = []
    dropped: list[str] = []
    used_chars = 0
    for row in records:
        separator_chars = 2 if selected else 0
        if used_chars + separator_chars + len(row.rendered) <= evidence_limit:
            selected.append(row)
            used_chars += separator_chars + len(row.rendered)
        else:
            dropped.append(row.identity)
    bounded = "\n\n".join(row.rendered for row in selected)
    prompt = prompt_builder(bounded)
    trace = _verifier_item_trace(
        selected=selected,
        dropped=dropped,
        original_records=original_records,
        required=required,
        required_slot_ids=required_slot_ids,
        bounded=bounded,
        prompt=prompt,
    )
    return prompt, bounded, trace


def _verifier_item_trace(
    *,
    selected: list[_EvidenceRow],
    dropped: list[str],
    original_records: list[_EvidenceRow],
    required: set[str],
    required_slot_ids: list[str] | None,
    bounded: str,
    prompt: str,
) -> dict[str, str]:
    content_was_packed = any(row.source_text != row.text for row in selected)
    trace = _budget_trace(
        status="item_packed" if dropped or content_was_packed else "full",
        original="\n\n".join(row.source_text for row in original_records),
        used=bounded,
        prompt=prompt,
    )
    required_selected = {
        required_id
        for required_id in required
        if any(required_id in row.aliases for row in selected)
    }
    required_coverage = len(required_selected) / len(required) if required else 1.0
    trace.update(
        {
            "verifier_input_evidence_ids": ",".join(row.identity for row in selected),
            "verifier_input_evidence_refs": ",".join(
                _row_evidence_refs(row) for row in selected
            ),
            "verifier_dropped_evidence_ids": ",".join(dropped),
            "verifier_input_character_count": str(len(bounded)),
            "verifier_input_token_count": str(len(re.findall(r"\S+", bounded))),
            "verifier_budget_exhausted": str(bool(dropped)).lower(),
            "verifier_required_evidence_ids": ",".join(sorted(required)),
            "verifier_required_slot_ids": ",".join(required_slot_ids or []),
            "verifier_required_evidence_coverage": f"{required_coverage:.6f}",
            "verifier_input_evidence_spans": json.dumps(
                [
                    {
                        "evidence_ref": f"{row.canonical_alias}:S{span_index}",
                        "evidence_id": row.identity,
                        "span_start": start,
                        "span_end": end,
                    }
                    for row in selected
                    for span_index, (start, end) in enumerate(row.spans, start=1)
                ],
                separators=(",", ":"),
            ),
            "verifier_evidence_alias_mapping": json.dumps(
                [
                    {
                        "evidence_ref": f"{row.canonical_alias}:S{span_index}",
                        "runtime_evidence_id": row.identity,
                        **canonical_prompt_span(
                            row.item,
                            text=row.source_text,
                            item_start=start,
                            item_end=end,
                        ),
                    }
                    for row in selected
                    for span_index, (start, end) in enumerate(row.spans, start=1)
                ],
                sort_keys=True,
                separators=(",", ":"),
            ),
        }
    )
    return trace


def _reserve_required_record_budget(
    records: list[_EvidenceRow],
    evidence_limit: int,
) -> list[_EvidenceRow]:
    required_records = [row for row in records if row.required]
    if not required_records:
        return records
    separator_budget = 2 * (len(required_records) - 1)
    per_required_limit = max(
        0,
        (evidence_limit - separator_budget) // len(required_records),
    )
    return [
        *(_fit_evidence_row(row, per_required_limit) for row in required_records),
        *(row for row in records if not row.required),
    ]


def _ranked_evidence_records(
    evidence_items: list[dict[str, Any]],
    *,
    question: str,
    candidate_answer: str,
    required: set[str],
    priority: set[str],
    claim_support: set[str],
    claim_contradiction: set[str],
) -> list[_EvidenceRow]:
    substantive_candidate = (
        "" if is_abstention_answer(candidate_answer) else candidate_answer
    )
    query_tokens = _content_tokens(f"{question} {substantive_candidate}")
    rows = _evidence_rows(
        evidence_items,
        question=question,
        query_tokens=query_tokens,
        required=required,
        priority=priority,
        claim_support=claim_support,
        claim_contradiction=claim_contradiction,
    )
    ordered_priority = [row for row in rows if row.required]
    seen_priority = {row.identity for row in ordered_priority}
    if not _looks_boolean(question):
        _append_relation_priority(
            ordered_priority,
            rows,
            seen_priority,
            question=question,
            candidate_answer=substantive_candidate,
        )
    for row in rows:
        if row.identity not in seen_priority and (
            row.claim_support or row.claim_contradiction
        ):
            ordered_priority.append(row)
            seen_priority.add(row.identity)
    _append_claim_priority(
        ordered_priority,
        rows,
        seen_priority,
        question=question,
        candidate_answer=substantive_candidate,
    )
    if _looks_boolean(question):
        _append_boolean_priority(ordered_priority, rows, seen_priority)
    return [
        *ordered_priority,
        *(row for row in rows if row.identity not in seen_priority),
    ]


def _evidence_rows(
    evidence_items: list[dict[str, Any]],
    *,
    question: str,
    query_tokens: set[str],
    required: set[str],
    priority: set[str],
    claim_support: set[str],
    claim_contradiction: set[str],
) -> list[_EvidenceRow]:
    rows: list[_EvidenceRow] = []
    seen: set[tuple[str, int, int, str]] = set()
    for index, item in enumerate(evidence_items):
        text = _item_text(item)
        if not text:
            continue
        try:
            evidence_id = identity_of(item).key
            aliases = exact_evidence_aliases(item)
        except ValueError:
            continue
        stable_key = canonical_evidence_sort_key(item, text=text)
        if stable_key in seen:
            continue
        seen.add(stable_key)
        span_texts: tuple[str, ...] = (text,)
        spans: tuple[tuple[int, int], ...] = ((0, len(text)),)
        if len(text) > 1200 and (_looks_boolean(question) or bool(required & aliases)):
            span_texts, spans = _boolean_proposition_snippet(
                text,
                question,
            )
        rendered_text = "\n".join(span_texts)
        relevance = len(query_tokens & _content_tokens(rendered_text))
        rows.append(
            _EvidenceRow(
                identity=evidence_id,
                aliases=frozenset(aliases),
                item=item,
                stable_key=stable_key,
                canonical_alias="",
                rendered="",
                text=rendered_text,
                source_text=text,
                span_texts=span_texts,
                index=index,
                relevance=relevance,
                required=bool(required & aliases),
                claim_support=bool(claim_support & aliases),
                claim_contradiction=bool(claim_contradiction & aliases),
                priority=bool(priority & aliases),
                spans=spans,
            )
        )
    rows.sort(
        key=lambda row: (
            -int(row.required),
            -int(row.claim_support),
            -int(row.claim_contradiction),
            -int(row.priority),
            -row.relevance,
            row.stable_key,
        )
    )
    return [
        _render_row(replace(row, canonical_alias=f"E{index}"))
        for index, row in enumerate(rows, start=1)
    ]


def _boolean_proposition_snippet(
    text: str,
    question: str,
) -> tuple[tuple[str, ...], tuple[tuple[int, int], ...]]:
    statements = [
        (match.start(), match.end(), match.group(0).strip())
        for match in re.finditer(r"[^.!?\n]+(?:[.!?]+|$)", text)
        if match.group(0).strip()
    ]
    if not statements:
        bounded = _truncate_evidence(text, 900)
        return (bounded,), ((0, len(bounded)),)
    question_tokens = stemmed_content_tokens(question)
    ranked = sorted(
        statements,
        key=lambda row: (
            -len(question_tokens & stemmed_content_tokens(row[2])),
            -int(_has_negation(row[2])),
            len(row[2]),
            row[0],
        ),
    )
    best = ranked[0]
    selected = [best]
    best_negative = _has_negation(best[2])
    opposite = next(
        (
            row
            for row in ranked[1:]
            if _has_negation(row[2]) is not best_negative
            and question_tokens & stemmed_content_tokens(row[2])
        ),
        None,
    )
    if opposite is not None:
        selected.append(opposite)
    selected.sort(key=lambda row: row[0])
    bounded_statements = [_truncate_evidence(row[2], 900) for row in selected]
    spans = tuple(
        (row[0], row[0] + len(bounded))
        for row, bounded in zip(selected, bounded_statements)
    )
    return tuple(bounded_statements), spans


def _fit_evidence_row(row: _EvidenceRow, limit: int) -> _EvidenceRow:
    if len(row.rendered) <= limit:
        return row
    prefix_budget = sum(
        len(f"[evidence_ref={row.canonical_alias}:S{index}]\n")
        for index in range(1, len(row.span_texts) + 1)
    )
    text_limit = max(0, limit - prefix_budget)
    selected_parts: list[str] = []
    selected_spans: list[tuple[int, int]] = []
    remaining = text_limit
    for part, (start, end) in zip(row.span_texts, row.spans):
        separator = 2 if selected_parts else 0
        if remaining <= separator:
            break
        bounded = _truncate_evidence(part, remaining - separator)
        if not bounded:
            break
        selected_parts.append(bounded)
        selected_spans.append((start, min(end, start + len(bounded))))
        remaining -= separator + len(bounded)
    text = "\n".join(selected_parts)
    spans = tuple(selected_spans)
    return _render_row(
        replace(
            row,
            rendered="",
            text=text,
            span_texts=tuple(selected_parts),
            spans=spans,
        )
    )


def _render_row(row: _EvidenceRow) -> _EvidenceRow:
    rendered = "\n\n".join(
        f"[evidence_ref={row.canonical_alias}:S{index}]\n{text}"
        for index, text in enumerate(row.span_texts, start=1)
    )
    return replace(row, rendered=rendered)


def _row_evidence_refs(row: _EvidenceRow) -> str:
    return ",".join(
        f"{row.canonical_alias}:S{index}" for index in range(1, len(row.spans) + 1)
    )


def _append_relation_priority(
    ordered: list[_EvidenceRow],
    rows: list[_EvidenceRow],
    seen: set[str],
    *,
    question: str,
    candidate_answer: str,
) -> None:
    question_tokens = stemmed_content_tokens(question)
    answer_text = re.sub(r"\\[a-zA-Z]+", " ", candidate_answer)
    answer_tokens = stemmed_content_tokens(answer_text) - question_tokens
    if not question_tokens or not answer_tokens:
        return
    candidates: list[tuple[tuple[int, int, int], _EvidenceRow, str]] = []
    for row in rows:
        if row.identity in seen:
            continue
        for statement in re.split(r"(?:\r?\n)+|(?<=[.!?])\s+", row.text):
            statement = statement.strip()
            statement_tokens = stemmed_content_tokens(statement)
            relation_hits = len(question_tokens & statement_tokens)
            answer_hits = len(answer_tokens & statement_tokens)
            if relation_hits and answer_hits:
                candidates.append(
                    (
                        (relation_hits, answer_hits, -len(statement)),
                        row,
                        statement,
                    )
                )
    if not candidates:
        return
    _score, row, statement = min(
        candidates,
        key=lambda value: (
            tuple(-part for part in value[0]),
            value[1].stable_key,
        ),
    )
    statement_start = row.source_text.find(statement)
    statement_end = statement_start + len(statement)
    ordered.append(
        _render_row(
            replace(
                row,
                text=statement,
                span_texts=(statement,),
                spans=((statement_start, statement_end),),
            )
        )
    )
    seen.add(row.identity)


def _append_claim_priority(
    ordered: list[_EvidenceRow],
    rows: list[_EvidenceRow],
    seen: set[str],
    *,
    question: str,
    candidate_answer: str,
) -> None:
    claim_texts = [
        value.strip()
        for value in re.split(r"(?<=[.!?;])\s+", candidate_answer)
        if value.strip()
    ] or [question]
    for claim in claim_texts:
        claim_tokens = _content_tokens(f"{question} {claim}")
        candidates = [row for row in rows if row.identity not in seen]
        if not candidates:
            return
        best = min(
            candidates,
            key=lambda row: (
                -len(claim_tokens & _content_tokens(row.text)),
                row.stable_key,
            ),
        )
        if claim_tokens & _content_tokens(best.text):
            ordered.append(best)
            seen.add(best.identity)


def _append_boolean_priority(
    ordered: list[_EvidenceRow],
    rows: list[_EvidenceRow],
    seen: set[str],
) -> None:
    for negative in (False, True):
        candidate = next(
            (
                row
                for row in rows
                if row.identity not in seen
                and _has_negation(row.text) is negative
                and row.relevance > 0
            ),
            None,
        )
        if candidate is not None:
            ordered.append(candidate)
            seen.add(candidate.identity)


def _normalized_ids(values: list[str] | None) -> set[str]:
    return {str(value).strip() for value in values or [] if str(value).strip()}


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
        "canonical_prompt_fingerprint": hashlib.sha256(
            prompt.encode("utf-8")
        ).hexdigest(),
    }
