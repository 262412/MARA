from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ktem.docqa.claim_filtering import clean_answer_text

from .metrics import is_abstention_answer
from .qasper_answerability_prompts import (
    json_structure_repair_prompt as _json_structure_repair_prompt,
)
from .qasper_boolean import boolean_candidate_polarity as _candidate_polarity
from .qasper_boolean import boolean_quote_is_grounded as _quote_is_grounded
from .qasper_boolean import boolean_relation_lemmas as _boolean_relation_lemmas
from .qasper_boolean import is_boolean_question as _is_boolean_question
from .qasper_boolean import (
    quality_control_relation_polarity as _quality_control_relation_polarity,
)
from .qasper_boolean_grounding import grounded_boolean_relation
from .qasper_boolean_prompt import (
    fit_boolean_verifier_prompt as _fit_boolean_verifier_prompt,
)
from .qasper_boolean_scope import evidence_item_text, validate_boolean_scope
from .qasper_deterministic_boolean import deterministic_closed_scope_result
from .qasper_free_text_answerability import verify_free_text_candidate
from .qasper_proposition_conflict import resolve_boolean_conflict
from .qasper_quote_support import (
    authoritative_quote_binding_trace,
    parse_boolean_verdict,
    quality_control_quote_for_verdict,
    resolve_verified_quote_support,
)

QASPER_ANSWERABILITY_CONTRACT = "qasper_answerability.v14"
QASPER_ANSWERABILITY_SEED = 20260724
QASPER_ANSWERABILITY_MAX_TOKENS = 192
QASPER_EVIDENCE_QUOTE_MAX_LENGTH = 640
QASPER_BOOLEAN_ANSWERABILITY_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "qasper_boolean_answerability",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "verdict": {
                    "type": "string",
                    "enum": [
                        "yes_complete",
                        "no_complete",
                        "yes_partial",
                        "no_partial",
                        "insufficient_evidence",
                    ],
                },
                "evidence_quote": {
                    "type": "string",
                    "maxLength": QASPER_EVIDENCE_QUOTE_MAX_LENGTH,
                },
            },
            "required": ["verdict", "evidence_quote"],
            "additionalProperties": False,
        },
    },
}

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)
_UNANSWERABLE_RE = re.compile(
    r"^(?:unanswerable|insufficient evidence|not enough evidence|"
    r"unable to answer|cannot answer)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class QasperAnswerabilityResult:
    answer: str
    trace: dict[str, Any]


def verify_qasper_answerability(
    llm: Any,
    *,
    question: str,
    evidence: str,
    evidence_items: list[dict[str, Any]] | None = None,
    required_evidence_ids: list[str] | None = None,
    required_slot_ids: list[str] | None = None,
    priority_evidence_ids: list[str] | None = None,
    claim_support_evidence_ids: list[str] | None = None,
    claim_contradiction_evidence_ids: list[str] | None = None,
    candidate_answer: str,
    answer_type: str = "",
) -> QasperAnswerabilityResult:
    candidate = _clean_candidate(candidate_answer)
    boolean_contract = str(
        answer_type or ""
    ).strip().lower() == "boolean" or _is_boolean_question(question)
    if not candidate:
        return QasperAnswerabilityResult(
            answer="",
            trace=_trace(
                "not_required",
                "",
                action="preserved_primary_answer",
            ),
        )
    if is_abstention_answer(candidate) or _UNANSWERABLE_RE.match(candidate):
        if boolean_contract:
            return _verify_boolean_candidate(
                llm,
                question=question,
                evidence=evidence,
                evidence_items=evidence_items,
                required_evidence_ids=required_evidence_ids,
                required_slot_ids=required_slot_ids,
                priority_evidence_ids=priority_evidence_ids,
                claim_support_evidence_ids=claim_support_evidence_ids,
                claim_contradiction_evidence_ids=(claim_contradiction_evidence_ids),
                candidate_answer="unanswerable",
                candidate="",
            )
        return QasperAnswerabilityResult(
            answer="unanswerable",
            trace=_trace(
                "not_required",
                "unanswerable",
                action="preserved_primary_answer",
                primary_answer="unanswerable",
            ),
        )
    candidate_polarity = _candidate_polarity(candidate)
    if boolean_contract:
        return _verify_boolean_candidate(
            llm,
            question=question,
            evidence=evidence,
            evidence_items=evidence_items,
            required_evidence_ids=required_evidence_ids,
            required_slot_ids=required_slot_ids,
            priority_evidence_ids=priority_evidence_ids,
            claim_support_evidence_ids=claim_support_evidence_ids,
            claim_contradiction_evidence_ids=claim_contradiction_evidence_ids,
            candidate_answer=candidate_answer,
            candidate=candidate_polarity,
        )
    return _verify_free_text_candidate(
        llm,
        question=question,
        evidence=evidence,
        evidence_items=evidence_items,
        required_evidence_ids=required_evidence_ids,
        required_slot_ids=required_slot_ids,
        priority_evidence_ids=priority_evidence_ids,
        claim_support_evidence_ids=claim_support_evidence_ids,
        claim_contradiction_evidence_ids=claim_contradiction_evidence_ids,
        candidate_answer=candidate_answer,
        candidate=candidate,
    )


def _verify_boolean_candidate(
    llm: Any,
    *,
    question: str,
    evidence: str,
    evidence_items: list[dict[str, Any]] | None,
    required_evidence_ids: list[str] | None,
    required_slot_ids: list[str] | None,
    priority_evidence_ids: list[str] | None,
    claim_support_evidence_ids: list[str] | None,
    claim_contradiction_evidence_ids: list[str] | None,
    candidate_answer: str,
    candidate: str,
) -> QasperAnswerabilityResult:
    candidate_polarity = _candidate_polarity(candidate)
    deterministic = deterministic_closed_scope_result(
        contract_id=QASPER_ANSWERABILITY_CONTRACT,
        question=question,
        evidence_items=evidence_items or [],
        candidate_polarity=candidate_polarity,
    )
    if deterministic is not None:
        answer, trace = deterministic
        return QasperAnswerabilityResult(
            answer=answer,
            trace=trace,
        )
    prompt, evidence, budget_trace = _fit_boolean_verifier_prompt(
        question=question,
        evidence=evidence,
        evidence_items=evidence_items,
        candidate_answer=candidate_answer,
        required_evidence_ids=required_evidence_ids,
        required_slot_ids=required_slot_ids,
        priority_evidence_ids=priority_evidence_ids,
        claim_support_evidence_ids=claim_support_evidence_ids,
        claim_contradiction_evidence_ids=claim_contradiction_evidence_ids,
    )
    verdict, quote, parse_trace = _call_verifier(
        llm,
        prompt,
        response_format=QASPER_BOOLEAN_ANSWERABILITY_RESPONSE_FORMAT,
        parser=parse_boolean_verdict,
        allowed_values=(
            "yes_complete",
            "no_complete",
            "yes_partial",
            "no_partial",
            "insufficient_evidence",
        ),
    )
    parse_trace = {**budget_trace, **parse_trace}
    if not verdict:
        return QasperAnswerabilityResult(
            answer=candidate_answer,
            trace=_trace(
                "error",
                "",
                action="preserved_primary_answer",
                parse_trace=parse_trace,
                primary_answer=candidate_polarity or "unanswerable",
            ),
        )
    quote = quality_control_quote_for_verdict(
        verdict,
        question,
        evidence_items or [],
        fallback=quote,
    )
    return _adjudicated_boolean_result(
        question=question,
        evidence=evidence,
        evidence_items=evidence_items,
        candidate_polarity=candidate_polarity,
        verdict=verdict,
        quote=quote,
        parse_trace=parse_trace,
    )


def _adjudicated_boolean_result(
    *,
    question: str,
    evidence: str,
    evidence_items: list[dict[str, Any]] | None,
    candidate_polarity: str,
    verdict: str,
    quote: str,
    parse_trace: dict[str, str],
) -> QasperAnswerabilityResult:
    (
        verdict,
        raw_verdict,
        quote_grounded,
        quote_supports_relation,
        reason,
        relation_trace,
    ) = _ground_boolean_verdict(
        question=question,
        evidence=evidence,
        verdict=verdict,
        quote=quote,
        evidence_items=evidence_items,
    )
    (
        verdict,
        quote_supports_relation,
        reason,
        authoritative_support,
    ) = resolve_verified_quote_support(
        question,
        quote,
        verdict,
        reason,
        quote_supports_relation,
        evidence_items,
        candidate_polarity=candidate_polarity,
    )
    action, answer, conflict_trace = _resolve_grounded_boolean_conflict(
        question,
        evidence,
        candidate_polarity,
        verdict=verdict,
        evidence_items=evidence_items,
        relation_trace=relation_trace,
        authoritative_support=authoritative_support,
    )
    relation_trace.update(conflict_trace)
    selected_answer = answer if answer in {"yes", "no"} else candidate_polarity
    if selected_answer:
        relation_trace.update(
            authoritative_quote_binding_trace(
                question,
                selected_answer,
                evidence_items or [],
                authoritative_support,
            )
        )
    return QasperAnswerabilityResult(
        answer=answer,
        trace=_trace(
            "ok",
            verdict,
            action=action,
            evidence_quote=quote,
            quote_grounded=quote_grounded,
            quote_supports_relation=quote_supports_relation,
            parse_trace={**parse_trace, **relation_trace},
            primary_answer=candidate_polarity or "unanswerable",
            adjudicated_polarity=verdict,
            raw_verifier_verdict=raw_verdict,
            reason=reason,
        ),
    )


def _resolve_grounded_boolean_conflict(
    question: str,
    evidence: str,
    candidate_polarity: str,
    *,
    verdict: str,
    evidence_items: list[dict[str, Any]] | None,
    relation_trace: dict[str, str],
    authoritative_support: Any,
) -> tuple[str, str, dict[str, str]]:
    scope_valid = relation_trace.get("boolean_scope_valid") != "false"
    return resolve_boolean_conflict(
        evidence if scope_valid else "",
        question,
        candidate_polarity=candidate_polarity if scope_valid else "",
        verdict=verdict,
        evidence_items=evidence_items if scope_valid else [],
        authoritative_claim_key=(
            authoritative_support.claim_key if authoritative_support else None
        ),
        authoritative_evidence_id=(
            authoritative_support.evidence_id if authoritative_support else ""
        ),
        authoritative_polarity=(
            authoritative_support.polarity if authoritative_support else ""
        ),
    )


def _ground_boolean_verdict(
    *,
    question: str,
    evidence: str,
    verdict: str,
    quote: str,
    evidence_items: list[dict[str, Any]] | None,
) -> tuple[str, str, bool, bool, str, dict[str, str]]:
    raw_verdict = verdict
    quality_control_polarity = (
        _quality_control_relation_polarity(question, quote) if quote else ""
    )
    relation_trace = {
        "question_relation_terms": ",".join(sorted(_boolean_relation_lemmas(question))),
        "quote_relation_terms": ",".join(sorted(_boolean_relation_lemmas(quote))),
    }
    quote_grounded = _quote_is_grounded(quote, evidence) or any(
        _quote_is_grounded(quote, evidence_item_text(item))
        for item in (evidence_items or [])
    )
    complete = {
        "yes_complete": "yes",
        "no_complete": "no",
    }
    typed_polarity = complete.get(raw_verdict, "")
    scope = (
        validate_boolean_scope(
            question,
            quote,
            typed_polarity,
            evidence_items=evidence_items,
        )
        if typed_polarity and quote_grounded
        else None
    )
    if scope is not None:
        relation_trace.update(scope.as_trace())
    (
        verdict,
        quote_supports_relation,
        reason,
        deterministic_conflict,
    ) = grounded_boolean_relation(
        raw_verdict,
        question=question,
        quote=quote,
        quote_grounded=quote_grounded,
        scope=scope,
    )
    if deterministic_conflict is not None:
        relation_trace["deterministic_relation_conflict"] = str(
            deterministic_conflict
        ).lower()
    if verdict in {"yes", "no"} and not quality_control_polarity:
        if scope is None:
            scope = validate_boolean_scope(
                question,
                quote,
                verdict,
                evidence_items=evidence_items,
            )
            relation_trace.update(scope.as_trace())
        if not scope.scope_valid:
            verdict = "insufficient_evidence"
            quote_supports_relation = False
            reason = scope.reason
    return (
        verdict,
        raw_verdict,
        quote_grounded,
        quote_supports_relation,
        reason,
        relation_trace,
    )


def _verify_free_text_candidate(
    llm: Any,
    *,
    question: str,
    evidence: str,
    evidence_items: list[dict[str, Any]] | None,
    required_evidence_ids: list[str] | None,
    required_slot_ids: list[str] | None,
    priority_evidence_ids: list[str] | None,
    claim_support_evidence_ids: list[str] | None,
    claim_contradiction_evidence_ids: list[str] | None,
    candidate_answer: str,
    candidate: str,
) -> QasperAnswerabilityResult:
    answer, trace = verify_free_text_candidate(
        llm,
        question=question,
        evidence=evidence,
        evidence_items=evidence_items,
        required_evidence_ids=required_evidence_ids,
        required_slot_ids=required_slot_ids,
        priority_evidence_ids=priority_evidence_ids,
        claim_support_evidence_ids=claim_support_evidence_ids,
        claim_contradiction_evidence_ids=claim_contradiction_evidence_ids,
        candidate_answer=candidate_answer,
        candidate=candidate,
        contract_id=QASPER_ANSWERABILITY_CONTRACT,
        seed=QASPER_ANSWERABILITY_SEED,
        max_tokens=QASPER_ANSWERABILITY_MAX_TOKENS,
    )
    return QasperAnswerabilityResult(answer=answer, trace=trace)


def _call_verifier(
    llm: Any,
    prompt: str,
    *,
    response_format: dict[str, Any],
    parser: Any,
    allowed_values: tuple[str, ...],
) -> tuple[str, str, dict[str, str]]:
    response = llm(
        prompt,
        max_tokens=QASPER_ANSWERABILITY_MAX_TOKENS,
        response_format=response_format,
        temperature=0,
        seed=QASPER_ANSWERABILITY_SEED,
    )
    initial_response = getattr(response, "text", "") or str(response)
    verdict, quote = parser(initial_response)
    if verdict:
        return (
            verdict,
            quote,
            {
                "parser_status": "ok",
                "repair_attempted": "false",
            },
        )
    if not _has_repairable_verdict(initial_response, allowed_values):
        return (
            "",
            "",
            {
                "parser_status": "error",
                "repair_attempted": "false",
                "repair_status": "not_repairable",
                "initial_response": str(initial_response),
            },
        )

    repair_response = llm(
        _json_structure_repair_prompt(
            initial_response,
            allowed_values=allowed_values,
        ),
        max_tokens=QASPER_ANSWERABILITY_MAX_TOKENS,
        response_format=response_format,
        temperature=0,
        seed=QASPER_ANSWERABILITY_SEED,
    )
    repaired_text = getattr(repair_response, "text", "") or str(repair_response)
    verdict, quote = parser(repaired_text)
    return (
        verdict,
        quote,
        {
            "parser_status": "ok" if verdict else "error",
            "repair_attempted": "true",
            "repair_status": "ok" if verdict else "error",
            "initial_response": str(initial_response),
            "repair_response": str(repaired_text),
        },
    )


def _has_repairable_verdict(
    response: str,
    allowed_values: tuple[str, ...],
) -> bool:
    lowered = str(response or "").lower()
    return any(
        re.search(rf'["\']?verdict["\']?\s*[:=]\s*["\']?{re.escape(value)}\b', lowered)
        for value in allowed_values
    )


def _clean_candidate(answer: str) -> str:
    return clean_answer_text(_THINK_BLOCK_RE.sub("", str(answer or ""))).rstrip(".")


def _trace(
    status: str,
    verdict: str,
    *,
    action: str = "",
    evidence_quote: str = "",
    quote_grounded: bool | None = None,
    quote_supports_relation: bool | None = None,
    parse_trace: dict[str, str] | None = None,
    primary_answer: str = "",
    adjudicated_polarity: str = "",
    raw_verifier_verdict: str = "",
    reason: str = "",
) -> dict[str, str]:
    trace = {
        "contract_id": QASPER_ANSWERABILITY_CONTRACT,
        "status": status,
        "verdict": verdict,
        "action": action,
    }
    if evidence_quote:
        trace["evidence_quote"] = evidence_quote
    if quote_grounded is not None:
        trace["quote_grounded"] = str(quote_grounded).lower()
    if quote_supports_relation is not None:
        trace["quote_supports_relation"] = str(quote_supports_relation).lower()
    if primary_answer:
        trace["primary_answer"] = primary_answer
    if adjudicated_polarity:
        trace["adjudicated_polarity"] = adjudicated_polarity
    if raw_verifier_verdict:
        trace["raw_verifier_verdict"] = raw_verifier_verdict
    if reason:
        trace["reason"] = reason
    trace.update(parse_trace or {})
    return trace
