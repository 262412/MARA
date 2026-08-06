from __future__ import annotations

import json
import re
from typing import Any

from ktem.docqa.evidence_identity import identity_of

from .qasper_answerability_prompts import (
    answerability_prompt,
    json_structure_repair_prompt,
)
from .qasper_boolean import stemmed_content_tokens
from .qasper_prompt_budget import compact_qasper_candidate, fit_qasper_verifier_items
from .qasper_quote_support import bind_evidence_ref_to_quote

_ALLOWED_VERDICTS = (
    "supported",
    "supported_with_pruning",
    "partially_supported",
    "conflicting_core",
    "insufficient_core_evidence",
    "unsupported",
)
_POSITIVE_VERDICTS = {
    "supported",
    "supported_with_pruning",
    "partially_supported",
}
QASPER_ANSWERABILITY_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "qasper_answerability",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "verdict": {"type": "string", "enum": list(_ALLOWED_VERDICTS)},
                "evidence_ref": {
                    "type": "string",
                    "maxLength": 32,
                    "pattern": "^(?:E[1-9][0-9]*:S[1-9][0-9]*)?$",
                },
                "evidence_quote": {"type": "string", "maxLength": 640},
                "revised_answer": {"type": "string"},
            },
            "required": [
                "verdict",
                "evidence_ref",
                "evidence_quote",
                "revised_answer",
            ],
            "additionalProperties": False,
        },
    },
}


def verify_free_text_candidate(
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
    candidate: str,
    contract_id: str,
    seed: int,
    max_tokens: int,
) -> tuple[str, dict[str, str]]:
    evidence_items, required_evidence_ids = _free_text_evidence_items(
        evidence,
        evidence_items,
        required_evidence_ids,
    )
    prompt, bounded_evidence, budget_trace = _fit_free_text_verifier_prompt(
        question=question,
        evidence=evidence,
        evidence_items=evidence_items,
        candidate=candidate,
        required_evidence_ids=required_evidence_ids,
        required_slot_ids=required_slot_ids,
        priority_evidence_ids=priority_evidence_ids,
        claim_support_evidence_ids=claim_support_evidence_ids,
        claim_contradiction_evidence_ids=claim_contradiction_evidence_ids,
    )
    verdict, evidence_ref, quote, revised_answer, parse_trace = _call_verifier(
        llm,
        prompt,
        seed=seed,
        max_tokens=max_tokens,
    )
    parse_trace = {**budget_trace, **parse_trace}
    if not verdict:
        return candidate_answer, _trace(
            contract_id,
            "error",
            "",
            "preserved_primary_answer",
            parse_trace=parse_trace,
        )
    return _free_text_decision(
        verdict,
        evidence_ref,
        quote,
        revised_answer,
        question=question,
        bounded_evidence=bounded_evidence,
        candidate=candidate,
        candidate_answer=candidate_answer,
        contract_id=contract_id,
        parse_trace=parse_trace,
        evidence_items=evidence_items,
    )


def _free_text_decision(
    verdict: str,
    evidence_ref: str,
    quote: str,
    revised_answer: str,
    *,
    question: str,
    bounded_evidence: str,
    candidate: str,
    candidate_answer: str,
    contract_id: str,
    parse_trace: dict[str, str],
    evidence_items: list[dict[str, Any]],
) -> tuple[str, dict[str, str]]:
    evidence_ref, binding_failure = _bound_positive_evidence_ref(
        verdict, evidence_ref, quote, evidence_items, parse_trace
    )
    if binding_failure:
        return _unsupported_free_text_decision(
            contract_id, parse_trace, binding_failure
        )
    quote_grounded = _quote_is_grounded(quote, bounded_evidence)
    relation_supported = _free_text_relation_supported(
        verdict, quote, question, candidate, revised_answer, quote_grounded
    )
    prunable_verdict = verdict not in {
        "conflicting_core",
        "insufficient_core_evidence",
    }
    pruned_answer = (
        _supported_candidate_core(
            candidate,
            quote=quote,
            question=question,
            revised_answer=revised_answer,
        )
        if prunable_verdict and quote_grounded
        else ""
    )
    if pruned_answer and _normalized(pruned_answer) != _normalized(candidate):
        return pruned_answer, _trace(
            contract_id,
            "ok",
            "supported_with_pruning",
            "pruned_unsupported_extension",
            evidence_ref=evidence_ref,
            evidence_quote=quote,
            quote_grounded=True,
            quote_supports_relation=True,
            parse_trace=parse_trace,
        )
    if verdict in _POSITIVE_VERDICTS and not relation_supported:
        return _unsupported_free_text_decision(
            contract_id,
            parse_trace,
            "grounded_quote_incomplete_relation",
        )

    answer, action = _answer_and_action(
        verdict,
        candidate_answer=candidate_answer,
        revised_answer=revised_answer,
    )
    return answer, _trace(
        contract_id,
        "ok",
        verdict,
        action,
        evidence_ref=evidence_ref if answer != "unanswerable" else "",
        evidence_quote=quote if answer != "unanswerable" else "",
        quote_grounded=quote_grounded if answer != "unanswerable" else False,
        quote_supports_relation=relation_supported,
        parse_trace=parse_trace,
    )


def _bound_positive_evidence_ref(
    verdict: str,
    evidence_ref: str,
    quote: str,
    evidence_items: list[dict[str, Any]],
    parse_trace: dict[str, str],
) -> tuple[str, str]:
    if verdict not in _POSITIVE_VERDICTS:
        return evidence_ref, ""
    resolved_ref, status = bind_evidence_ref_to_quote(
        evidence_ref,
        quote,
        evidence_items,
        parse_trace.get("verifier_evidence_alias_mapping", ""),
    )
    return resolved_ref, "" if resolved_ref else status


def _free_text_relation_supported(
    verdict: str,
    quote: str,
    question: str,
    candidate: str,
    revised_answer: str,
    quote_grounded: bool,
) -> bool:
    supported_answer = (
        revised_answer
        if verdict in {"supported_with_pruning", "partially_supported"}
        else candidate
    )
    return quote_grounded and _quote_supports_relation(
        quote,
        question,
        supported_answer,
    )


def _unsupported_free_text_decision(
    contract_id: str,
    parse_trace: dict[str, str],
    reason: str,
) -> tuple[str, dict[str, str]]:
    return "unanswerable", _trace(
        contract_id,
        "ok",
        "unsupported",
        "abstained_ungrounded_quote",
        quote_grounded=False,
        quote_supports_relation=False,
        reason=reason,
        parse_trace=parse_trace,
    )


def _fit_free_text_verifier_prompt(
    *,
    question: str,
    evidence: str,
    evidence_items: list[dict[str, Any]] | None,
    candidate: str,
    required_evidence_ids: list[str] | None,
    required_slot_ids: list[str] | None,
    priority_evidence_ids: list[str] | None,
    claim_support_evidence_ids: list[str] | None,
    claim_contradiction_evidence_ids: list[str] | None,
) -> tuple[str, str, dict[str, str]]:
    bounded_candidate = compact_qasper_candidate(candidate)

    def prompt_builder(bounded: str) -> str:
        return answerability_prompt(
            question=question,
            evidence=bounded,
            candidate_answer=bounded_candidate,
        )

    prompt, bounded_evidence, trace = fit_qasper_verifier_items(
        evidence_items or [],
        prompt_builder,
        question=question,
        candidate_answer=bounded_candidate,
        required_evidence_ids=required_evidence_ids,
        required_slot_ids=required_slot_ids,
        priority_evidence_ids=priority_evidence_ids,
        claim_support_evidence_ids=claim_support_evidence_ids,
        claim_contradiction_evidence_ids=claim_contradiction_evidence_ids,
    )
    trace.update(
        {
            "candidate_chars_original": str(len(candidate)),
            "candidate_chars_used": str(len(bounded_candidate)),
        }
    )
    return prompt, bounded_evidence, trace


def _free_text_evidence_items(
    evidence: str,
    evidence_items: list[dict[str, Any]] | None,
    required_evidence_ids: list[str] | None,
) -> tuple[list[dict[str, Any]], list[str] | None]:
    if evidence_items is not None:
        return evidence_items, required_evidence_ids
    raw_item = {
        "evidence_id": "raw-evidence",
        "source_id": "raw-evidence",
        "evaluation_source_id": "raw-evidence",
        "document_id": "raw-evidence",
        "text": evidence,
    }
    raw_identity = identity_of(raw_item).key
    required = list(required_evidence_ids or [])
    if raw_identity not in required:
        required.append(raw_identity)
    return [raw_item], required


def _supported_candidate_core(
    candidate: str,
    *,
    quote: str,
    question: str,
    revised_answer: str,
) -> str:
    revised = str(revised_answer or "").strip()
    if revised and _quote_supports_relation(quote, question, revised):
        return revised
    clauses = _candidate_answer_clauses(candidate, question=question)
    supported = [
        clause
        for clause in clauses
        if _candidate_clause_is_grounded(quote, question, clause)
    ]
    return "; ".join(supported)


def _candidate_clause_is_grounded(quote: str, question: str, clause: str) -> bool:
    if not _quote_supports_relation(quote, question, clause):
        return False
    question_tokens = stemmed_content_tokens(question)
    answer_tokens = stemmed_content_tokens(clause) - question_tokens
    if not answer_tokens:
        return False
    quote_tokens = stemmed_content_tokens(quote)
    return len(quote_tokens & answer_tokens) / len(answer_tokens) >= 0.75


def _candidate_answer_clauses(candidate: str, *, question: str) -> list[str]:
    text = str(candidate or "")
    latex_phrases = [
        " ".join(match.split())
        for match in re.findall(r"\\text\{([^{}]+)\}", text)
        if " ".join(match.split())
    ]
    question_tokens = stemmed_content_tokens(question)
    answer_phrases = [
        phrase
        for phrase in latex_phrases
        if stemmed_content_tokens(phrase) - question_tokens
    ]
    if answer_phrases:
        return list(dict.fromkeys(answer_phrases))
    clauses: list[str] = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        sentence = re.sub(
            r"^.*?\b(?:include(?:s|d|ing)?|consists?\s+of|comprises?)\s+",
            "",
            sentence,
            count=1,
            flags=re.IGNORECASE,
        )
        clauses.extend(
            clause.strip(" ,.;:")
            for clause in re.split(
                r"\s*[,;]\s*|\s+(?:and|but|while|whereas)\s+|\s*\+\s*",
                sentence,
                flags=re.IGNORECASE,
            )
            if clause.strip(" ,.;:")
        )
    return list(dict.fromkeys(clauses))


def _normalized(value: str) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _call_verifier(
    llm: Any,
    prompt: str,
    *,
    seed: int,
    max_tokens: int,
) -> tuple[str, str, str, str, dict[str, str]]:
    response = llm(
        prompt,
        max_tokens=max_tokens,
        response_format=QASPER_ANSWERABILITY_RESPONSE_FORMAT,
        temperature=0,
        seed=seed,
    )
    response_text = getattr(response, "text", "") or str(response)
    verdict, evidence_ref, quote, revised_answer = _verdict(response_text)
    if verdict or not _has_repairable_verdict(response_text):
        return (
            verdict,
            evidence_ref,
            quote,
            revised_answer,
            _initial_parse_trace(verdict, response_text),
        )

    repair_response = llm(
        json_structure_repair_prompt(
            response_text,
            allowed_values=_ALLOWED_VERDICTS,
            include_evidence_ref=True,
            include_revised_answer=True,
        ),
        max_tokens=max_tokens,
        response_format=QASPER_ANSWERABILITY_RESPONSE_FORMAT,
        temperature=0,
        seed=seed,
    )
    repaired_text = getattr(repair_response, "text", "") or str(repair_response)
    verdict, evidence_ref, quote, revised_answer = _verdict(repaired_text)
    return (
        verdict,
        evidence_ref,
        quote,
        revised_answer,
        {
            "parser_status": "ok" if verdict else "error",
            "repair_attempted": "true",
            "repair_status": "ok" if verdict else "error",
            "initial_response": str(response_text),
            "repair_response": str(repaired_text),
        },
    )


def _initial_parse_trace(verdict: str, response: str) -> dict[str, str]:
    trace = {
        "parser_status": "ok" if verdict else "error",
        "repair_attempted": "false",
    }
    if not verdict:
        trace.update(
            {
                "repair_status": "not_repairable",
                "initial_response": str(response),
            }
        )
    return trace


def _verdict(answer: str) -> tuple[str, str, str, str]:
    try:
        payload = json.loads(str(answer or ""))
    except json.JSONDecodeError:
        return "", "", "", ""
    if not isinstance(payload, dict):
        return "", "", "", ""
    verdict = str(payload.get("verdict") or "")
    if verdict not in _ALLOWED_VERDICTS:
        return "", "", "", ""
    evidence_ref = str(payload.get("evidence_ref") or "").strip()
    quote = str(payload.get("evidence_quote") or "").strip()
    if verdict == "insufficient_core_evidence":
        evidence_ref = ""
        quote = ""
    return (
        verdict,
        evidence_ref,
        quote,
        str(payload.get("revised_answer") or "").strip(),
    )


def _has_repairable_verdict(response: str) -> bool:
    lowered = str(response or "").lower()
    return any(
        re.search(
            rf'["\']?verdict["\']?\s*[:=]\s*["\']?{re.escape(value)}\b',
            lowered,
        )
        for value in _ALLOWED_VERDICTS
    )


def _answer_and_action(
    verdict: str,
    *,
    candidate_answer: str,
    revised_answer: str,
) -> tuple[str, str]:
    if verdict == "supported":
        return candidate_answer, "confirmed_candidate"
    if verdict in {"supported_with_pruning", "partially_supported"}:
        if revised_answer:
            return revised_answer, "pruned_unsupported_extension"
        return "unanswerable", "abstained_insufficient_core_evidence"
    if verdict == "conflicting_core":
        return "unanswerable", "abstained_conflicting_core"
    if verdict == "unsupported":
        return "unanswerable", "abstained_unsupported_candidate"
    return "unanswerable", "abstained_insufficient_core_evidence"


def _quote_supports_relation(quote: str, question: str, candidate: str) -> bool:
    quote_tokens = stemmed_content_tokens(quote)
    candidate_tokens = stemmed_content_tokens(candidate)
    if not candidate_tokens:
        return False
    question_tokens = stemmed_content_tokens(question)
    answer_tokens = candidate_tokens - question_tokens
    support_tokens = answer_tokens or candidate_tokens
    candidate_coverage = len(quote_tokens & support_tokens) / len(support_tokens)
    question_anchors = question_tokens - candidate_tokens
    required_anchors = min(2, len(question_anchors))
    lexical_relation = (
        candidate_coverage >= 0.5
        and required_anchors > 0
        and len(quote_tokens & question_anchors) >= required_anchors
    )
    return lexical_relation or (
        candidate_coverage >= 0.5
        and _semantic_question_relation_supported(question, quote, candidate)
    )


def _semantic_question_relation_supported(
    question: str,
    quote: str,
    candidate: str,
) -> bool:
    question_tokens = stemmed_content_tokens(question)
    quote_tokens = stemmed_content_tokens(quote)
    candidate_tokens = stemmed_content_tokens(candidate)
    if {"backg", "knowl"} & question_tokens and (
        {"knowl", "prior"} & quote_tokens
        or {"label", "feature"} <= (quote_tokens | candidate_tokens)
    ):
        return True
    if {"use", "lever"} & question_tokens and (
        {"use", "lever", "provi"} & (quote_tokens | candidate_tokens)
    ):
        return True
    return False


def _quote_is_grounded(quote: str, evidence: str) -> bool:
    normalized_quote = " ".join(str(quote or "").lower().split())
    normalized_evidence = " ".join(str(evidence or "").lower().split())
    return len(normalized_quote) >= 8 and normalized_quote in normalized_evidence


def _trace(
    contract_id: str,
    status: str,
    verdict: str,
    action: str,
    *,
    evidence_ref: str = "",
    evidence_quote: str = "",
    quote_grounded: bool | None = None,
    quote_supports_relation: bool | None = None,
    parse_trace: dict[str, str] | None = None,
    reason: str = "",
) -> dict[str, str]:
    trace = {
        "contract_id": contract_id,
        "status": status,
        "verdict": verdict,
        "action": action,
    }
    if evidence_ref:
        trace["evidence_ref"] = evidence_ref
    if evidence_quote:
        trace["evidence_quote"] = evidence_quote
    if quote_grounded is not None:
        trace["quote_grounded"] = str(quote_grounded).lower()
    if quote_supports_relation is not None:
        trace["quote_supports_relation"] = str(quote_supports_relation).lower()
    if reason:
        trace["reason"] = reason
    trace.update(parse_trace or {})
    return trace
