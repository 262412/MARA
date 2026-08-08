from __future__ import annotations

import re
from typing import Any

from .qasper_answerability_prompts import json_structure_repair_prompt


def call_boolean_verifier(
    llm: Any,
    prompt: str,
    *,
    response_format: dict[str, Any],
    parser: Any,
    allowed_values: tuple[str, ...],
    max_tokens: int,
    seed: int,
) -> tuple[str, str, str, dict[str, str]]:
    response = llm(
        prompt,
        max_tokens=max_tokens,
        response_format=response_format,
        temperature=0,
        top_p=1,
        seed=seed,
    )
    initial_response = getattr(response, "text", "") or str(response)
    verdict, evidence_ref, quote = parser(initial_response)
    if verdict:
        return verdict, evidence_ref, quote, _parse_trace("ok", False, seed)
    if not _has_repairable_verdict(initial_response, allowed_values):
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
    repair_response = llm(
        json_structure_repair_prompt(
            initial_response,
            allowed_values=allowed_values,
            include_evidence_ref=True,
        ),
        max_tokens=max_tokens,
        response_format=response_format,
        temperature=0,
        top_p=1,
        seed=seed,
    )
    repaired_text = getattr(repair_response, "text", "") or str(repair_response)
    verdict, evidence_ref, quote = parser(repaired_text)
    return (
        verdict,
        evidence_ref,
        quote,
        {
            **_parse_trace("ok" if verdict else "error", True, seed),
            "repair_status": "ok" if verdict else "error",
            "initial_response": str(initial_response),
            "repair_response": str(repaired_text),
        },
    )


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
