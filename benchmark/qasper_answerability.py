from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from ktem.docqa.claim_filtering import clean_answer_text

from .metrics import is_abstention_answer
from .qasper_authority import required_authority_is_missing
from .qasper_boolean import boolean_candidate_polarity as _candidate_polarity
from .qasper_boolean import is_boolean_question as _is_boolean_question
from .qasper_boolean_adjudication import adjudicate_boolean
from .qasper_boolean_prompt import (
    fit_boolean_verifier_prompt as _fit_boolean_verifier_prompt,
)
from .qasper_boolean_verifier import call_boolean_verifier
from .qasper_deterministic_boolean import deterministic_closed_scope_result
from .qasper_free_text_answerability import verify_free_text_candidate
from .qasper_quote_support import (
    evidence_ref_for_quote,
    parse_boolean_verdict,
    quality_control_quote_for_verdict,
)

QASPER_ANSWERABILITY_CONTRACT = "qasper_answerability.v15"
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
                "evidence_ref": {
                    "type": "string",
                    "maxLength": 32,
                    "pattern": "^(?:E[1-9][0-9]*:S[1-9][0-9]*)?$",
                },
            },
            "required": ["verdict", "evidence_ref", "evidence_quote"],
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
    missing_required_slot_ids: list[str] | None = None,
    missing_required_evidence_ids: list[str] | None = None,
    priority_evidence_ids: list[str] | None = None,
    claim_support_evidence_ids: list[str] | None = None,
    claim_contradiction_evidence_ids: list[str] | None = None,
    candidate_answer: str,
    answer_type: str = "",
) -> QasperAnswerabilityResult:
    candidate = _clean_candidate(candidate_answer)
    boolean_contract = _uses_boolean_contract(question, answer_type)
    if not candidate:
        return _preserved_empty_candidate()
    if is_abstention_answer(candidate) or _UNANSWERABLE_RE.match(candidate):
        if boolean_contract:
            return _verify_boolean_candidate(
                llm,
                question=question,
                evidence=evidence,
                evidence_items=evidence_items,
                required_evidence_ids=required_evidence_ids,
                required_slot_ids=required_slot_ids,
                missing_required_slot_ids=missing_required_slot_ids,
                missing_required_evidence_ids=missing_required_evidence_ids,
                priority_evidence_ids=priority_evidence_ids,
                claim_support_evidence_ids=claim_support_evidence_ids,
                claim_contradiction_evidence_ids=(claim_contradiction_evidence_ids),
                candidate_answer="unanswerable",
                candidate="",
            )
        return _preserved_abstention_candidate()
    candidate_polarity = _candidate_polarity(candidate)
    if boolean_contract:
        return _verify_boolean_candidate(
            llm,
            question=question,
            evidence=evidence,
            evidence_items=evidence_items,
            required_evidence_ids=required_evidence_ids,
            required_slot_ids=required_slot_ids,
            missing_required_slot_ids=missing_required_slot_ids,
            missing_required_evidence_ids=missing_required_evidence_ids,
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
        missing_required_slot_ids=missing_required_slot_ids,
        missing_required_evidence_ids=missing_required_evidence_ids,
        priority_evidence_ids=priority_evidence_ids,
        claim_support_evidence_ids=claim_support_evidence_ids,
        claim_contradiction_evidence_ids=claim_contradiction_evidence_ids,
        candidate_answer=candidate_answer,
        candidate=candidate,
    )


def _uses_boolean_contract(question: str, answer_type: str) -> bool:
    return str(answer_type or "").strip().lower() == "boolean" or _is_boolean_question(
        question
    )


def _preserved_empty_candidate() -> QasperAnswerabilityResult:
    return QasperAnswerabilityResult(
        answer="",
        trace=_trace(
            "not_required",
            "",
            action="preserved_primary_answer",
        ),
    )


def _preserved_abstention_candidate() -> QasperAnswerabilityResult:
    return QasperAnswerabilityResult(
        answer="unanswerable",
        trace=_trace(
            "not_required",
            "unanswerable",
            action="preserved_primary_answer",
            primary_answer="unanswerable",
        ),
    )


def _verify_boolean_candidate(
    llm: Any,
    *,
    question: str,
    evidence: str,
    evidence_items: list[dict[str, Any]] | None,
    required_evidence_ids: list[str] | None,
    required_slot_ids: list[str] | None,
    missing_required_slot_ids: list[str] | None,
    missing_required_evidence_ids: list[str] | None,
    priority_evidence_ids: list[str] | None,
    claim_support_evidence_ids: list[str] | None,
    claim_contradiction_evidence_ids: list[str] | None,
    candidate_answer: str,
    candidate: str,
) -> QasperAnswerabilityResult:
    candidate_polarity = _candidate_polarity(candidate)
    evidence_items = _boolean_evidence_items(evidence, evidence_items)
    prompt, evidence, budget_trace = _fit_boolean_verifier_prompt(
        question=question,
        evidence=evidence,
        evidence_items=evidence_items,
        candidate_answer=candidate_answer,
        required_evidence_ids=required_evidence_ids,
        required_slot_ids=required_slot_ids,
        missing_required_slot_ids=missing_required_slot_ids,
        missing_required_evidence_ids=missing_required_evidence_ids,
        priority_evidence_ids=priority_evidence_ids,
        claim_support_evidence_ids=claim_support_evidence_ids,
        claim_contradiction_evidence_ids=claim_contradiction_evidence_ids,
    )
    if required_authority_is_missing(budget_trace):
        return QasperAnswerabilityResult(
            answer="unanswerable",
            trace=_trace(
                "ok",
                "insufficient_evidence",
                action="abstained_missing_required_evidence",
                parse_trace=budget_trace,
                primary_answer=candidate_polarity or "unanswerable",
                adjudicated_polarity="insufficient_evidence",
                reason="missing_required_evidence_authority",
            ),
        )
    deterministic_result = _deterministic_boolean_result(
        question=question,
        evidence=evidence,
        evidence_items=evidence_items,
        candidate_polarity=candidate_polarity,
        budget_trace=budget_trace,
    )
    if deterministic_result is not None:
        return deterministic_result
    return _model_boolean_result(
        llm,
        prompt=prompt,
        question=question,
        evidence=evidence,
        evidence_items=evidence_items,
        candidate_answer=candidate_answer,
        candidate_polarity=candidate_polarity,
        budget_trace=budget_trace,
    )


def _boolean_evidence_items(
    evidence: str,
    evidence_items: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if evidence_items is not None:
        return evidence_items
    return [
        {
            "evidence_id": "raw-evidence",
            "source_id": "raw-evidence",
            "evaluation_source_id": "raw-evidence",
            "document_id": "raw-evidence",
            "section_id": "unknown",
            "text": evidence,
        }
    ]


def _deterministic_boolean_result(
    *,
    question: str,
    evidence: str,
    evidence_items: list[dict[str, Any]],
    candidate_polarity: str,
    budget_trace: dict[str, str],
) -> QasperAnswerabilityResult | None:
    deterministic = deterministic_closed_scope_result(
        contract_id=QASPER_ANSWERABILITY_CONTRACT,
        question=question,
        evidence_items=evidence_items,
        candidate_polarity=candidate_polarity,
    )
    if deterministic is None:
        return None
    deterministic_polarity, deterministic_trace = deterministic
    quote = str(deterministic_trace.get("evidence_quote") or "")
    evidence_ref = evidence_ref_for_quote(
        quote,
        evidence_items,
        budget_trace.get("verifier_evidence_alias_mapping", ""),
    )
    return _adjudicated_boolean_result(
        question=question,
        evidence=evidence,
        evidence_items=evidence_items,
        candidate_polarity=candidate_polarity,
        verdict=f"{deterministic_polarity}_complete",
        evidence_ref=evidence_ref,
        quote=quote,
        parse_trace={
            **budget_trace,
            "parser_status": "not_called_deterministic_scope",
            "deterministic_scope_proposal": "true",
        },
    )


def _model_boolean_result(
    llm: Any,
    *,
    prompt: str,
    question: str,
    evidence: str,
    evidence_items: list[dict[str, Any]],
    candidate_answer: str,
    candidate_polarity: str,
    budget_trace: dict[str, str],
) -> QasperAnswerabilityResult:
    verdict, evidence_ref, quote, parse_trace = call_boolean_verifier(
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
        max_tokens=QASPER_ANSWERABILITY_MAX_TOKENS,
        seed=QASPER_ANSWERABILITY_SEED,
        repair_context=_boolean_repair_context(question, evidence),
        allowed_evidence_refs=tuple(
            value.strip()
            for value in budget_trace.get("verifier_input_evidence_refs", "").split(",")
            if value.strip()
        ),
    )
    parse_trace = {**budget_trace, **parse_trace}
    if not verdict:
        return _invalid_boolean_verifier_result(
            candidate_answer=candidate_answer,
            candidate_polarity=candidate_polarity,
            parse_trace=parse_trace,
        )
    original_quote = quote
    quote = quality_control_quote_for_verdict(
        verdict,
        question,
        evidence_items,
        fallback=quote,
    )
    if quote != original_quote:
        evidence_ref = evidence_ref_for_quote(
            quote,
            evidence_items,
            budget_trace.get("verifier_evidence_alias_mapping", ""),
        )
    elif not evidence_ref:
        evidence_ref = evidence_ref_for_quote(
            quote,
            evidence_items,
            budget_trace.get("verifier_evidence_alias_mapping", ""),
        )
    return _adjudicated_boolean_result(
        question=question,
        evidence=evidence,
        evidence_items=evidence_items,
        candidate_polarity=candidate_polarity,
        verdict=verdict,
        evidence_ref=evidence_ref,
        quote=quote,
        parse_trace=parse_trace,
    )


def _boolean_repair_context(question: str, evidence: str) -> str:
    return f"QUESTION:\n{question}\n\nPACKED EVIDENCE:\n{evidence}"


def _invalid_boolean_verifier_result(
    *,
    candidate_answer: str,
    candidate_polarity: str,
    parse_trace: dict[str, str],
) -> QasperAnswerabilityResult:
    repair_failed = (
        parse_trace.get("repair_attempted") == "true"
        and parse_trace.get("repair_status") == "error"
    )
    return QasperAnswerabilityResult(
        answer="unanswerable" if repair_failed else candidate_answer,
        trace=_trace(
            "error",
            "",
            action=(
                "abstained_invalid_verifier_repair"
                if repair_failed
                else "preserved_primary_answer"
            ),
            parse_trace=parse_trace,
            primary_answer=candidate_polarity or "unanswerable",
            reason="invalid_verifier_schema_after_repair" if repair_failed else "",
        ),
    )


def _adjudicated_boolean_result(
    *,
    question: str,
    evidence: str,
    evidence_items: list[dict[str, Any]] | None,
    candidate_polarity: str,
    verdict: str,
    evidence_ref: str,
    quote: str,
    parse_trace: dict[str, str],
) -> QasperAnswerabilityResult:
    resolved = adjudicate_boolean(
        question=question,
        evidence=evidence,
        evidence_items=evidence_items,
        candidate_polarity=candidate_polarity,
        verdict=verdict,
        evidence_ref=evidence_ref,
        quote=quote,
        parse_trace=parse_trace,
    )
    return QasperAnswerabilityResult(
        answer=resolved.answer,
        trace=_trace(
            "ok",
            resolved.verdict,
            action=resolved.action,
            evidence_ref=resolved.evidence_ref,
            evidence_quote=resolved.quote,
            quote_grounded=resolved.quote_grounded,
            quote_supports_relation=resolved.quote_supports_relation,
            parse_trace={**parse_trace, **resolved.relation_trace},
            primary_answer=candidate_polarity or "unanswerable",
            adjudicated_polarity=resolved.verdict,
            raw_verifier_verdict=resolved.raw_verdict,
            reason=resolved.reason,
        ),
    )


def _verify_free_text_candidate(
    llm: Any,
    *,
    question: str,
    evidence: str,
    evidence_items: list[dict[str, Any]] | None,
    required_evidence_ids: list[str] | None,
    required_slot_ids: list[str] | None,
    missing_required_slot_ids: list[str] | None,
    missing_required_evidence_ids: list[str] | None,
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
        missing_required_slot_ids=missing_required_slot_ids,
        missing_required_evidence_ids=missing_required_evidence_ids,
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


def _clean_candidate(answer: str) -> str:
    return clean_answer_text(_THINK_BLOCK_RE.sub("", str(answer or ""))).rstrip(".")


def _trace(
    status: str,
    verdict: str,
    *,
    action: str = "",
    evidence_ref: str = "",
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
    if evidence_ref:
        trace["evidence_ref"] = evidence_ref
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
