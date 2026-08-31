from __future__ import annotations

from collections.abc import Mapping
from typing import Any, TypeGuard

from .qasper_semantic_pack_contract import canonical_payload_digest
from .question_proposition import QuestionProposition
from .semantic_relation_clause_lexical import canonical_proposition_object_token_set

_ALIGNMENT_CONTRACT = "qasper_selector_semantic_alignment.v1"


def verified_frozen_object_span(
    premise: Mapping[str, Any],
    proposition: QuestionProposition,
    *,
    declared_slots: list[str],
) -> dict[str, Any] | None:
    """Return a source-bound canonical object contribution, when fully attested."""

    if "object" not in declared_slots:
        return None
    identity = _premise_identity(premise)
    if identity is None:
        return None
    alignment = _verified_alignment(
        premise,
        proposition,
        identity=identity,
        declared_slots=declared_slots,
    )
    if alignment is None:
        return None
    ranges = _verified_alignment_match_ranges(
        alignment["semantic_matches"],
        identity=identity,
    )
    raw_span = dict(premise.get("proposition_slot_spans") or {}).get("object")
    if not ranges or not isinstance(raw_span, Mapping):
        return None
    return _verified_child_span(raw_span, identity=identity, match_ranges=ranges)


def _premise_identity(premise: Mapping[str, Any]) -> dict[str, Any] | None:
    quote = str(premise.get("quote") or "")
    selector_id = str(premise.get("span_selector") or "")
    evidence_id = str(premise.get("evidence_id") or "")
    event_id = str(premise.get("event_id") or "")
    start = premise.get("span_start")
    end = premise.get("span_end")
    if (
        not all((quote, selector_id, evidence_id, event_id))
        or not _plain_int(start)
        or not _plain_int(end)
        or end - start != len(quote)
    ):
        return None
    identity = {
        "quote": quote,
        "selector_id": selector_id,
        "evidence_id": evidence_id,
        "event_id": event_id,
        "span_start": start,
        "span_end": end,
    }
    return identity


def _verified_alignment(
    premise: Mapping[str, Any],
    proposition: QuestionProposition,
    *,
    identity: Mapping[str, Any],
    declared_slots: list[str],
) -> dict[str, Any] | None:
    raw = premise.get("semantic_alignment")
    if not isinstance(raw, Mapping):
        return None
    alignment = dict(raw)
    expected = {
        "contract_id": _ALIGNMENT_CONTRACT,
        "status": "verified",
        "proposition_id": proposition.proposition_id,
        "evidence_id": identity["evidence_id"],
        "selector_id": identity["selector_id"],
        "span_start": identity["span_start"],
        "span_end": identity["span_end"],
        "text_digest": canonical_payload_digest(identity["quote"]),
        "event_id": identity["event_id"],
    }
    digest_payload = {
        key: value for key, value in alignment.items() if key != "alignment_digest"
    }
    slot_refs = alignment.get("slot_refs")
    required = alignment.get("required_object_tokens")
    covered = alignment.get("covered_object_tokens")
    matches = alignment.get("semantic_matches")
    required_tokens = canonical_proposition_object_token_set(proposition)
    covered_tokens = (
        {str(token) for token in covered}
        if isinstance(covered, (list, tuple, set))
        else set()
    )
    if (
        any(alignment.get(key) != value for key, value in expected.items())
        or alignment.get("alignment_digest") != canonical_payload_digest(digest_payload)
        or not isinstance(slot_refs, Mapping)
        or set(slot_refs) != set(declared_slots)
        or any(str(value) != identity["selector_id"] for value in slot_refs.values())
        or not isinstance(required, (list, tuple, set))
        or {str(token) for token in required} != required_tokens
        or not covered_tokens <= required_tokens
        or not isinstance(matches, Mapping)
        or {str(token) for token in matches} != covered_tokens
    ):
        return None
    return alignment


def _verified_alignment_match_ranges(
    matches: Mapping[str, Any],
    *,
    identity: Mapping[str, Any],
) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    quote = str(identity["quote"])
    parent_start = int(identity["span_start"])
    parent_end = int(identity["span_end"])
    for raw_matches in matches.values():
        if not isinstance(raw_matches, (list, tuple)) or not raw_matches:
            return []
        for match in raw_matches:
            if not isinstance(match, Mapping):
                return []
            start = match.get("span_start")
            end = match.get("span_end")
            text = str(match.get("text") or "")
            if not _plain_int(start) or not _plain_int(end):
                return []
            if (
                not parent_start <= start < end <= parent_end
                or quote[start - parent_start : end - parent_start] != text
                or match.get("match_kind") not in {"exact", "synonym"}
                or not str(match.get("rule_id") or "")
            ):
                return []
            ranges.append((start, end))
    return ranges


def _verified_child_span(
    raw_span: Mapping[str, Any],
    *,
    identity: Mapping[str, Any],
    match_ranges: list[tuple[int, int]],
) -> dict[str, Any] | None:
    parent_start = int(identity["span_start"])
    parent_end = int(identity["span_end"])
    selector_id = str(identity["selector_id"])
    quote = str(identity["quote"])
    child_start = raw_span.get("span_start")
    child_end = raw_span.get("span_end")
    clause_start = raw_span.get("clause_start")
    clause_end = raw_span.get("clause_end")
    child_text = str(raw_span.get("text") or "")
    if (
        not _plain_int(child_start)
        or not _plain_int(child_end)
        or not _plain_int(clause_start)
        or not _plain_int(clause_end)
    ):
        return None
    expected_ref = f"{selector_id}#semantic-slot:object:{child_start}:{child_end}"
    if (
        not parent_start
        <= clause_start
        <= child_start
        < child_end
        <= clause_end
        <= parent_end
        or any(
            not child_start <= start < end <= child_end for start, end in match_ranges
        )
        or quote[child_start - parent_start : child_end - parent_start] != child_text
        or raw_span.get("parent_selector_id") != selector_id
        or raw_span.get("parent_span_start") != parent_start
        or raw_span.get("parent_span_end") != parent_end
        or raw_span.get("parent_text_digest") != canonical_payload_digest(quote)
        or raw_span.get("text_digest") != canonical_payload_digest(child_text)
        or raw_span.get("evidence_ref") != expected_ref
    ):
        return None
    return {
        "text": child_text,
        "span_start": child_start - parent_start,
        "span_end": child_end - parent_start,
        "clause_ref": str(raw_span.get("clause_ref") or ""),
        "clause_start": clause_start - parent_start,
        "clause_end": clause_end - parent_start,
    }


def _plain_int(value: Any) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool)
