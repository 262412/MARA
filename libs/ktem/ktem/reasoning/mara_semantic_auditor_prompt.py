"""Canonical, reference-based serialization for semantic auditor evidence."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Collection, Mapping
from typing import Any

from ktem.docqa.question_proposition import (
    QuestionProposition,
    TypedConclusion,
    proposition_evidence_bindings,
)

SEMANTIC_ENTAILMENT_AUDIT_MAX_PROMPT_CHARS = 8000
SEMANTIC_AUDITOR_EVIDENCE_SERIALIZATION_CONTRACT = (
    "semantic_auditor_controlled_evidence.v1"
)


def semantic_entailment_audit_prompt(
    proposition: QuestionProposition,
    conclusion: TypedConclusion,
    proof_mode: str,
    premises: list[dict[str, Any]],
    *,
    original_candidate: str = "",
    candidate_judgment: str = "",
    premise_slot_evidence: Mapping[str, Mapping[str, Any]] | None = None,
    semantic_pack_identity: Mapping[str, str] | None = None,
) -> str:
    prompt = semantic_entailment_audit_prompt_unbounded(
        proposition,
        conclusion,
        proof_mode,
        premises,
        original_candidate=original_candidate,
        candidate_judgment=candidate_judgment,
        premise_slot_evidence=premise_slot_evidence,
        semantic_pack_identity=semantic_pack_identity,
    )
    if len(prompt) > SEMANTIC_ENTAILMENT_AUDIT_MAX_PROMPT_CHARS:
        raise ValueError("Semantic entailment audit prompt exceeded its bound.")
    return prompt


def semantic_entailment_audit_prompt_unbounded(
    proposition: QuestionProposition,
    conclusion: TypedConclusion,
    proof_mode: str,
    premises: list[dict[str, Any]],
    *,
    original_candidate: str = "",
    candidate_judgment: str = "",
    premise_slot_evidence: Mapping[str, Mapping[str, Any]] | None = None,
    semantic_pack_identity: Mapping[str, str] | None = None,
) -> str:
    payload = semantic_entailment_audit_payload(
        proposition,
        conclusion,
        proof_mode,
        premises,
        original_candidate=original_candidate,
        candidate_judgment=candidate_judgment,
        premise_slot_evidence=premise_slot_evidence,
        semantic_pack_identity=semantic_pack_identity,
    )
    return "/no_think\nAUDIT THIS PROOF PROPOSAL:\n" + json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def semantic_entailment_audit_payload(
    proposition: QuestionProposition,
    conclusion: TypedConclusion,
    proof_mode: str,
    premises: list[dict[str, Any]],
    *,
    original_candidate: str,
    candidate_judgment: str,
    premise_slot_evidence: Mapping[str, Mapping[str, Any]] | None,
    semantic_pack_identity: Mapping[str, str] | None,
) -> dict[str, Any]:
    controlled_spans: list[dict[str, Any]] = []
    serialized_premises: list[dict[str, Any]] = []
    for index, premise in enumerate(premises, start=1):
        label = f"P{index}"
        span_records, premise_record = _controlled_premise(
            label,
            premise,
            premise_slot_evidence=premise_slot_evidence,
        )
        controlled_spans.extend(span_records)
        serialized_premises.append(premise_record)
    return {
        "original_candidate": str(original_candidate or "").strip().casefold(),
        "candidate_judgment": str(candidate_judgment or "").strip().casefold(),
        "question_proposition": proposition.as_dict(),
        "typed_conclusion": conclusion.as_dict(),
        "semantic_pack_identity": dict(semantic_pack_identity or {}),
        "proof_mode": proof_mode,
        "target_proposition_slot_bindings": proposition_evidence_bindings(proposition),
        "evidence_serialization": {
            "contract_id": SEMANTIC_AUDITOR_EVIDENCE_SERIALIZATION_CONTRACT,
            "text_policy": "serialize_each_frozen_span_once_then_ref_digest",
        },
        "frozen_evidence_spans": controlled_spans,
        "premises": serialized_premises,
    }


def _controlled_premise(
    label: str,
    premise: Mapping[str, Any],
    *,
    premise_slot_evidence: Mapping[str, Mapping[str, Any]] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    quote = str(premise.get("quote") or "")
    quote_ref = f"{label}:quote"
    quote_digest = _text_digest(quote)
    quote_start = _integer_or_none(premise.get("span_start"))
    quote_end = _integer_or_none(premise.get("span_end"))
    spans = [
        {
            "evidence_ref": quote_ref,
            "selector_ref": str(premise.get("span_selector") or ""),
            "text": quote,
            "text_digest": quote_digest,
            "span_start": quote_start,
            "span_end": quote_end,
        }
    ]
    fragment = str(premise.get("proposition_fragment") or "")
    fragment_ref = quote_ref if fragment == quote else f"{label}:fragment"
    if fragment_ref != quote_ref:
        spans.append(_fragment_span(fragment_ref, fragment, quote, quote_start))
    slots = list(premise.get("binds_proposition_slots") or [])
    return spans, {
        "premise_ref": label,
        "frozen_span_ref": quote_ref,
        "frozen_span_digest": quote_digest,
        "proposition_fragment_ref": fragment_ref,
        "proposition_fragment_digest": _text_digest(fragment),
        "binds_proposition_slots": slots,
        "local_proposition_slot_contributions": _controlled_slot_evidence(
            label,
            quote_ref,
            quote,
            quote_start,
            slots,
            premise_slot_evidence=premise_slot_evidence,
        ),
        "semantic_alignment": _controlled_alignment(
            label,
            quote_ref,
            premise.get("semantic_alignment"),
        ),
        "evidence_relation": str(premise.get("evidence_relation") or ""),
    }


def _fragment_span(
    evidence_ref: str,
    fragment: str,
    quote: str,
    quote_start: int | None,
) -> dict[str, Any]:
    relative_start = quote.find(fragment)
    absolute_start = (
        quote_start + relative_start
        if quote_start is not None and relative_start >= 0
        else None
    )
    return {
        "evidence_ref": evidence_ref,
        "text": fragment,
        "text_digest": _text_digest(fragment),
        "span_start": absolute_start,
        "span_end": absolute_start + len(fragment)
        if absolute_start is not None
        else None,
    }


def _controlled_slot_evidence(
    label: str,
    quote_ref: str,
    quote: str,
    quote_start: int | None,
    slots: Collection[Any],
    *,
    premise_slot_evidence: Mapping[str, Mapping[str, Any]] | None,
) -> dict[str, Any]:
    evidence = dict((premise_slot_evidence or {}).get(label) or {})
    return {
        str(slot): _controlled_slot(
            label,
            str(slot),
            quote_ref,
            quote,
            quote_start,
            evidence.get(str(slot)),
            strict=premise_slot_evidence is not None,
        )
        for slot in slots
    }


def _controlled_slot(
    label: str,
    slot: str,
    quote_ref: str,
    quote: str,
    quote_start: int | None,
    value: Any,
    *,
    strict: bool,
) -> dict[str, Any]:
    if not strict or not isinstance(value, Mapping):
        return {"evidence_ref": f"{label}:{slot}", "source_span_ref": quote_ref}
    text = str(value.get("text") or "")
    start = _integer_or_none(value.get("span_start"))
    end = _integer_or_none(value.get("span_end"))
    controlled: dict[str, Any] = {
        "evidence_ref": str(value.get("evidence_ref") or ""),
        "source_span_ref": quote_ref,
        "text_digest": _text_digest(text),
        "clause_ref": str(value.get("clause_ref") or ""),
    }
    relative = _frozen_span_relative_offsets(
        quote,
        quote_start,
        text,
        start,
        end,
    )
    if relative is not None:
        controlled["relative_start"], controlled["relative_end"] = relative
    else:
        controlled["span_start"] = start
        controlled["span_end"] = end
        controlled["coordinate_basis"] = "unresolved"
    return controlled


def _frozen_span_relative_offsets(
    quote: str,
    quote_start: int | None,
    text: str,
    start: int | None,
    end: int | None,
) -> tuple[int, int] | None:
    if start is None or end is None:
        return None
    if quote_start is not None:
        relative_start = start - quote_start
        relative_end = end - quote_start
        if quote[relative_start:relative_end] == text:
            return relative_start, relative_end
    if quote[start:end] == text:
        return start, end
    return None


def _controlled_alignment(
    label: str,
    quote_ref: str,
    value: Any,
) -> dict[str, Any]:
    alignment = dict(value) if isinstance(value, Mapping) else {}
    projected = {
        key: alignment.get(key)
        for key in (
            "contract_id",
            "status",
            "alignment_digest",
        )
        if key in alignment
    }
    projected["evidence_ref"] = f"{label}:semantic_alignment"
    projected["source_span_ref"] = quote_ref
    return projected


def _text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _integer_or_none(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
