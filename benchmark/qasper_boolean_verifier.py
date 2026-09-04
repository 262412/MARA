from __future__ import annotations

import re
from typing import Any

from .qasper_answerability_prompts import json_structure_repair_prompt
from .qasper_prompt_budget import QASPER_VERIFIER_PROMPT_MAX_CHARS
from .qasper_prompt_budget_utils import truncate_evidence


def call_boolean_verifier(
    llm: Any,
    prompt: str,
    *,
    response_format: dict[str, Any],
    parser: Any,
    allowed_values: tuple[str, ...],
    max_tokens: int,
    seed: int,
    repair_context: str = "",
    allowed_evidence_refs: tuple[str, ...] = (),
    quote_ref_resolver: Any = None,
) -> tuple[str, str, str, dict[str, str]]:
    response = _call_verifier(llm, prompt, max_tokens, response_format, seed)
    initial_response = getattr(response, "text", "") or str(response)
    verdict, evidence_ref, quote = parser(initial_response)
    initial_evidence_ref = evidence_ref
    structural_repair = _needs_structural_repair(
        verdict,
        evidence_ref,
        quote,
        allowed_evidence_refs,
    )
    evidence_ref, validation_status, quote_ref_valid = _validate_quote_ref(
        verdict,
        evidence_ref,
        quote,
        quote_ref_resolver,
    )
    identity_cannot_be_repaired = not allowed_evidence_refs and validation_status in {
        "evidence_ref_unresolved",
        "quote_identity_unresolved",
    }
    needs_repair = structural_repair or (
        not quote_ref_valid and not identity_cannot_be_repaired
    )
    if verdict and not needs_repair:
        return (
            verdict,
            evidence_ref,
            quote,
            {
                **_parse_trace("ok", False, seed),
                "quote_ref_validation_status": validation_status,
            },
        )
    if not verdict and not _has_repairable_verdict(initial_response, allowed_values):
        return (
            "",
            "",
            "",
            {
                **_parse_trace("error", False, seed),
                "repair_status": "not_repairable",
                "initial_response": str(initial_response),
            },
        )
    return _repair_boolean_verifier(
        llm,
        initial_response,
        initial_evidence_ref,
        response_format=response_format,
        parser=parser,
        allowed_values=allowed_values,
        max_tokens=max_tokens,
        seed=seed,
        repair_context=repair_context,
        allowed_evidence_refs=allowed_evidence_refs,
        quote_ref_resolver=quote_ref_resolver,
    )


def _repair_boolean_verifier(
    llm: Any,
    initial_response: str,
    initial_evidence_ref: str,
    *,
    response_format: dict[str, Any],
    parser: Any,
    allowed_values: tuple[str, ...],
    max_tokens: int,
    seed: int,
    repair_context: str,
    allowed_evidence_refs: tuple[str, ...],
    quote_ref_resolver: Any,
) -> tuple[str, str, str, dict[str, str]]:
    preserve_evidence_ref = bool(initial_evidence_ref) and (
        not allowed_evidence_refs or initial_evidence_ref in allowed_evidence_refs
    )
    repair_prompt, repair_prompt_truncated = _bounded_repair_prompt(
        initial_response,
        allowed_values=allowed_values,
        repair_context=repair_context,
        allowed_evidence_refs=allowed_evidence_refs,
        preserve_evidence_ref=preserve_evidence_ref,
    )
    repair_response = _call_verifier(
        llm, repair_prompt, max_tokens, response_format, seed
    )
    repaired_text = getattr(repair_response, "text", "") or str(repair_response)
    verdict, evidence_ref, quote = parser(repaired_text)
    evidence_ref, validation_status, quote_ref_valid = _validate_quote_ref(
        verdict,
        evidence_ref,
        quote,
        quote_ref_resolver,
    )
    repaired_needs_repair = (
        _needs_structural_repair(
            verdict,
            evidence_ref,
            quote,
            allowed_evidence_refs,
        )
        or not quote_ref_valid
    )
    return (
        ("" if repaired_needs_repair else verdict),
        ("" if repaired_needs_repair else evidence_ref),
        ("" if repaired_needs_repair else quote),
        {
            **_parse_trace(
                "ok" if verdict and not repaired_needs_repair else "error", True, seed
            ),
            "repair_status": "ok" if verdict and not repaired_needs_repair else "error",
            "repair_prompt_chars": str(len(repair_prompt)),
            "repair_prompt_truncated": str(repair_prompt_truncated).lower(),
            "initial_response": str(initial_response),
            "repair_response": str(repaired_text),
            "quote_ref_validation_status": validation_status,
        },
    )


def _validate_quote_ref(
    verdict: str,
    evidence_ref: str,
    quote: str,
    resolver: Any,
) -> tuple[str, str, bool]:
    if verdict == "insufficient_evidence":
        return evidence_ref, "not_applicable", True
    if verdict not in {"yes_complete", "no_complete", "yes_partial", "no_partial"}:
        return evidence_ref, "not_checked", True
    if not evidence_ref or not quote or resolver is None:
        return evidence_ref, "not_checked", resolver is None
    resolved_ref, status = resolver(evidence_ref, quote)
    if status == "bound" and resolved_ref:
        return resolved_ref, status, True
    if status == "evidence_ref_rebound" and resolved_ref:
        return resolved_ref, status, True
    return evidence_ref, status, False


def _call_verifier(
    llm: Any,
    prompt: str,
    max_tokens: int,
    response_format: dict[str, Any],
    seed: int,
) -> Any:
    return llm(
        prompt,
        max_tokens=max_tokens,
        response_format=response_format,
        temperature=0,
        top_p=1,
        seed=seed,
    )


def _bounded_repair_prompt(
    response: str,
    *,
    allowed_values: tuple[str, ...],
    repair_context: str,
    allowed_evidence_refs: tuple[str, ...],
    preserve_evidence_ref: bool,
) -> tuple[str, bool]:
    repair_response_text = response

    def render(context: str, refs: tuple[str, ...]) -> str:
        return json_structure_repair_prompt(
            repair_response_text,
            allowed_values=allowed_values,
            include_evidence_ref=True,
            evidence_context=context,
            allowed_evidence_refs=refs,
            preserve_evidence_ref=preserve_evidence_ref,
        )

    prompt = render(repair_context, allowed_evidence_refs)
    if len(prompt) <= QASPER_VERIFIER_PROMPT_MAX_CHARS:
        return prompt, False

    refs = allowed_evidence_refs
    base = render("", refs)
    if len(base) >= QASPER_VERIFIER_PROMPT_MAX_CHARS:
        refs = ()
        base = render("", refs)
    if len(base) >= QASPER_VERIFIER_PROMPT_MAX_CHARS:
        repair_response_text = _repairable_response_excerpt(
            response,
            allowed_values,
        )
        base = render("", refs)
    context_marker = render("x", refs)
    context_overhead = len(context_marker) - len(base) - 1
    context_limit = max(
        0,
        QASPER_VERIFIER_PROMPT_MAX_CHARS - len(base) - context_overhead,
    )
    bounded_context = truncate_evidence(repair_context, context_limit)
    prompt = render(bounded_context, refs)
    if len(prompt) > QASPER_VERIFIER_PROMPT_MAX_CHARS:
        overflow = len(prompt) - QASPER_VERIFIER_PROMPT_MAX_CHARS
        bounded_context = truncate_evidence(
            bounded_context,
            max(0, len(bounded_context) - overflow),
        )
        prompt = render(bounded_context, refs)
    truncated = (
        bounded_context != repair_context
        or refs != allowed_evidence_refs
        or repair_response_text != response
    )
    return prompt, truncated


def _repairable_response_excerpt(
    response: str,
    allowed_values: tuple[str, ...],
    *,
    max_chars: int = 1200,
) -> str:
    text = str(response or "")
    match = next(
        (
            match
            for value in allowed_values
            if (
                match := re.search(
                    rf'["\']?verdict["\']?\s*[:=]\s*["\']?{re.escape(value)}\b',
                    text,
                    flags=re.IGNORECASE,
                )
            )
        ),
        None,
    )
    if match is None:
        return truncate_evidence(text, max_chars)
    start = max(0, match.start() - max_chars // 4)
    return truncate_evidence(text[start:], max_chars)


def _needs_structural_repair(
    verdict: str,
    evidence_ref: str,
    quote: str,
    allowed_evidence_refs: tuple[str, ...],
) -> bool:
    if verdict == "insufficient_evidence":
        return False
    # A complete/partial proposition must carry both pieces of quote lineage.
    if verdict not in {"yes_complete", "no_complete", "yes_partial", "no_partial"}:
        return False
    if not evidence_ref or not quote:
        return True
    if allowed_evidence_refs and evidence_ref not in allowed_evidence_refs:
        return True
    return False


def _parse_trace(status: str, repaired: bool, seed: int) -> dict[str, str]:
    return {
        "parser_status": status,
        "repair_attempted": str(repaired).lower(),
        "verifier_temperature": "0",
        "verifier_top_p": "1",
        "verifier_seed": str(seed),
    }


def _has_repairable_verdict(
    response: str,
    allowed_values: tuple[str, ...],
) -> bool:
    lowered = str(response or "").lower()
    return any(
        re.search(rf'["\']?verdict["\']?\s*[:=]\s*["\']?{re.escape(value)}\b', lowered)
        for value in allowed_values
    )
