from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from ktem.docqa.canonical_proposition_evidence_plan_contract import (
    canonical_predicate_match_kind,
)
from ktem.docqa.qasper_semantic_pack_contract import canonical_payload_digest
from ktem.docqa.question_proposition import (
    QuestionProposition,
    applicable_proposition_evidence_slots,
    build_question_proposition,
)
from ktem.docqa.semantic_relation_clause_lexical import (
    canonical_proposition_object_token_set,
    canonical_semantic_token,
)
from ktem.docqa.semantic_relation_clause_validation import (
    semantic_relation_clause_analysis,
)

from .mara_qasper_selector_semantic_alignment_contract import (
    ALIGNMENT_CONTRACT,
    CURRENT_PAPER_ANALYSIS_HEADING_RE,
    OBJECT_SYNONYM_RULES,
)

_SEMANTIC_TOKEN_RE = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?")
_AUDITABLE_INSPECTION_RE = re.compile(
    r"\b(?:analys(?:e|es|ed|ing|is)|examine|examines|examined|examining|"
    r"inspect(?:s|ed|ing)?|investigat(?:e|es|ed|ing|ion)|"
    r"visualiz(?:e|es|ed|ing|ation)|visualis(?:e|es|ed|ing|ation))\b",
    re.IGNORECASE,
)


def predicate_surface_is_auditable(
    proposition: QuestionProposition,
    text: str,
) -> bool:
    return proposition.predicate != "inspect" or bool(
        _AUDITABLE_INSPECTION_RE.search(text)
    )


def auditable_target_relation_present(question: str, text: str) -> bool:
    proposition = build_question_proposition(question)
    analysis = semantic_relation_clause_analysis(
        {
            "quote": text,
            "binds_proposition_slots": list(
                applicable_proposition_evidence_slots(proposition)
            ),
        },
        proposition,
    )
    return bool(
        analysis.get("target_relation_present") is True
        and predicate_surface_is_auditable(proposition, text)
    )


def build_local_selector_semantic_alignment(
    question: str,
    selector: Mapping[str, Any],
    semantics: Mapping[str, Any],
) -> dict[str, Any] | None:
    proposition = build_question_proposition(question)
    identity = _selector_identity(selector)
    if identity is None:
        return None
    required = canonical_proposition_object_token_set(proposition)
    matches = _selector_object_semantic_matches(
        identity["text"],
        span_start=identity["span_start"],
        required_tokens=required,
        object_bearing="object" in set(semantics.get("slots") or ()),
    )
    slots, rule_ids, actor_attested = _aligned_slots(
        proposition,
        identity["text"],
        semantics,
        matches,
    )
    predicate_kind = _predicate_match_kind(proposition, semantics, slots)
    direct_covered = {
        str(token)
        for token in dict(semantics.get("analysis") or {}).get(
            "covered_object_tokens", ()
        )
    } & required
    if (
        not (set(matches) - direct_covered)
        and not actor_attested
        and (predicate_kind != "paraphrase")
    ):
        return None
    local_state = _alignment_local_state(semantics, slots)
    if local_state is None:
        return None
    return _alignment_payload(
        proposition,
        identity,
        slots=slots,
        required=required,
        matches=matches,
        rule_ids=rule_ids,
        predicate_kind=predicate_kind,
        local_state=local_state,
    )


def attested_selector_slot_span(
    selector: Mapping[str, Any],
    slot: str,
) -> dict[str, Any]:
    selector_id = str(selector.get("selector_id") or "")
    start = int(selector.get("span_start") or 0)
    end = int(selector.get("span_end") or 0)
    text = str(selector.get("text") or "")
    digest = canonical_payload_digest(text)
    return {
        "evidence_ref": f"{selector_id}#semantic-slot:{slot}:{start}:{end}",
        "text": text,
        "span_start": start,
        "span_end": end,
        "clause_ref": f"{selector_id}#semantic-clause",
        "clause_start": start,
        "clause_end": end,
        "parent_selector_id": selector_id,
        "parent_span_start": start,
        "parent_span_end": end,
        "parent_text_digest": digest,
        "text_digest": digest,
    }


def attested_selector_alignment_slot_span(
    selector: Mapping[str, Any],
    alignment: Mapping[str, Any],
    slot: str,
    *,
    base_span: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Project one verified alignment to an exact source-bound slot span."""

    if slot != "object":
        return attested_selector_slot_span(selector, slot)
    matches = [
        match
        for raw_matches in dict(alignment.get("semantic_matches") or {}).values()
        if isinstance(raw_matches, (list, tuple))
        for match in raw_matches
        if isinstance(match, Mapping)
    ]
    if not matches:
        return attested_selector_slot_span(selector, slot)
    start = min(int(match["span_start"]) for match in matches)
    end = max(int(match["span_end"]) for match in matches)
    selector_start = int(selector.get("span_start") or 0)
    selector_end = int(selector.get("span_end") or 0)
    text = str(selector.get("text") or "")
    local_start = start - selector_start
    local_end = end - selector_start
    if not (
        selector_start <= start < end <= selector_end
        and 0 <= local_start < local_end <= len(text)
    ):
        return attested_selector_slot_span(selector, slot)
    selector_id = str(selector.get("selector_id") or "")
    child_text = text[local_start:local_end]
    clause_ref = str((base_span or {}).get("clause_ref") or "")
    clause_start = (base_span or {}).get("clause_start")
    clause_end = (base_span or {}).get("clause_end")
    return {
        "evidence_ref": f"{selector_id}#semantic-slot:{slot}:{start}:{end}",
        "text": child_text,
        "span_start": start,
        "span_end": end,
        "clause_ref": clause_ref or f"{selector_id}#semantic-clause",
        "clause_start": (
            clause_start if isinstance(clause_start, int) else selector_start
        ),
        "clause_end": clause_end if isinstance(clause_end, int) else selector_end,
        "parent_selector_id": selector_id,
        "parent_span_start": selector_start,
        "parent_span_end": selector_end,
        "parent_text_digest": canonical_payload_digest(text),
        "text_digest": canonical_payload_digest(child_text),
    }


def _selector_identity(selector: Mapping[str, Any]) -> dict[str, Any] | None:
    text = str(selector.get("text") or "")
    identity = {
        "text": text,
        "selector_id": str(selector.get("selector_id") or ""),
        "evidence_id": str(selector.get("evidence_id") or ""),
        "event_id": str(selector.get("event_id") or ""),
        "span_start": selector.get("span_start"),
        "span_end": selector.get("span_end"),
    }
    start = identity["span_start"]
    end = identity["span_end"]
    if (
        not all(
            identity[key] for key in ("text", "selector_id", "evidence_id", "event_id")
        )
        or not isinstance(start, int)
        or isinstance(start, bool)
        or not isinstance(end, int)
        or isinstance(end, bool)
        or end - start != len(text)
    ):
        return None
    return identity


def _aligned_slots(
    proposition: QuestionProposition,
    text: str,
    semantics: Mapping[str, Any],
    matches: Mapping[str, Any],
) -> tuple[list[str], set[str], bool]:
    observed = set(semantics.get("slots") or ())
    slots = [
        slot
        for slot in applicable_proposition_evidence_slots(proposition)
        if slot in observed
    ]
    rule_ids = {
        str(match.get("rule_id") or "")
        for values in matches.values()
        for match in values
    }
    actor_attested = bool(
        proposition.actor == "current_paper"
        and "actor" not in slots
        and "predicate" in slots
        and CURRENT_PAPER_ANALYSIS_HEADING_RE.search(text)
    )
    if actor_attested:
        slots.insert(0, "actor")
        rule_ids.add("current_paper_analysis_heading")
    return slots, rule_ids, actor_attested


def _predicate_match_kind(
    proposition: QuestionProposition,
    semantics: Mapping[str, Any],
    slots: list[str],
) -> str:
    predicate_span = dict(semantics.get("slot_spans") or {}).get("predicate")
    if isinstance(predicate_span, Mapping):
        return canonical_predicate_match_kind(
            proposition,
            str(predicate_span.get("text") or ""),
        )
    return "paraphrase" if "predicate" in slots else "missing"


def _alignment_local_state(
    semantics: Mapping[str, Any],
    slots: list[str],
) -> str | None:
    if "predicate" not in slots:
        return "unbound"
    local_state = str(semantics.get("local_relation_state") or "")
    return (
        local_state
        if local_state in {"affirmative_assertion", "explicit_contradiction"}
        else None
    )


def _alignment_payload(
    proposition: QuestionProposition,
    identity: Mapping[str, Any],
    *,
    slots: list[str],
    required: set[str],
    matches: Mapping[str, Any],
    rule_ids: set[str],
    predicate_kind: str,
    local_state: str,
) -> dict[str, Any]:
    payload = {
        "contract_id": ALIGNMENT_CONTRACT,
        "status": "verified",
        "proposition_id": proposition.proposition_id,
        "evidence_id": identity["evidence_id"],
        "selector_id": identity["selector_id"],
        "span_start": identity["span_start"],
        "span_end": identity["span_end"],
        "text_digest": canonical_payload_digest(identity["text"]),
        "event_id": identity["event_id"],
        "slot_refs": {slot: identity["selector_id"] for slot in slots},
        "required_object_tokens": sorted(required),
        "covered_object_tokens": sorted(matches),
        "semantic_matches": dict(matches),
        "semantic_rule_ids": sorted(rule_ids),
        "predicate_concept": proposition.predicate,
        "predicate_match_kind": predicate_kind,
        "polarity_relation": {
            "explicit_contradiction": "explicit_contradiction",
            "affirmative_assertion": "proposition_support",
            "unbound": "undetermined",
        }[local_state],
        "local_relation_state": local_state,
    }
    payload["alignment_digest"] = canonical_payload_digest(payload)
    return payload


def _selector_object_semantic_matches(
    text: str,
    *,
    span_start: int,
    required_tokens: set[str],
    object_bearing: bool,
) -> dict[str, list[dict[str, Any]]]:
    matches: dict[str, list[dict[str, Any]]] = {}
    for token_match in _SEMANTIC_TOKEN_RE.finditer(text):
        token = canonical_semantic_token(token_match.group(0))
        if token not in required_tokens or token in matches:
            continue
        matches[token] = [
            _semantic_match_payload(
                token_match,
                text,
                span_start=span_start,
                match_kind="exact",
                rule_id="exact_semantic_token",
            )
        ]
    if not object_bearing:
        return matches
    for token in sorted(required_tokens - set(matches)):
        for rule_id, pattern in OBJECT_SYNONYM_RULES.get(token, ()):
            if match := pattern.search(text):
                matches[token] = [
                    _semantic_match_payload(
                        match,
                        text,
                        span_start=span_start,
                        match_kind="synonym",
                        rule_id=rule_id,
                    )
                ]
                break
    return matches


def _semantic_match_payload(
    match: re.Match[str],
    text: str,
    *,
    span_start: int,
    match_kind: str,
    rule_id: str,
) -> dict[str, Any]:
    return {
        "text": text[match.start() : match.end()],
        "span_start": span_start + match.start(),
        "span_end": span_start + match.end(),
        "match_kind": match_kind,
        "rule_id": rule_id,
    }
