from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from .calculation_evidence_identity import calculation_evidence_lookup
from .evidence_schema import EvidenceBundle
from .evidence_text import extract_final_answer_text

_NUMBER_RE = re.compile(r"(?<![A-Za-z0-9])(?:[$€£¥]\s*)?\(?[+-]?\d[\d,]*(?:\.\d+)?\)?")
_SCALE_TERMS = {"thousand", "million", "billion"}


@dataclass(frozen=True, slots=True)
class CalculationClaimResult:
    claim: str
    status: str
    supporting_evidence_ids: tuple[str, ...] = ()
    contradicting_evidence_ids: tuple[str, ...] = ()


def calculation_claim_result(
    bundle: EvidenceBundle,
    answer: str,
    claims: list[str],
    *,
    domain: str,
) -> CalculationClaimResult | None:
    if domain != "finance":
        return None
    trace = dict(bundle.metadata.get("finance_numeric_trace") or {})
    plan = dict(trace.get("calculation_plan") or {})
    verification = dict(trace.get("calculation_verification") or {})
    execution = dict(trace.get("calculation_execution") or {})
    if not trace or not verification.get("valid") or execution.get("status") != "ok":
        return None
    expected = _decimal(execution.get("value"))
    if expected is None:
        return None
    rendered = extract_final_answer_text(answer)
    claim = _result_claim(claims, rendered, expected)
    citation_ids = tuple(
        dict.fromkeys(
            str(value).strip()
            for value in execution.get("citation_ids") or []
            if str(value or "").strip()
        )
    )
    evidence_lookup = calculation_evidence_lookup(bundle.items)
    matched_ids = tuple(
        citation_id for citation_id in citation_ids if citation_id in evidence_lookup
    )
    if not citation_ids or matched_ids != citation_ids:
        return CalculationClaimResult(claim=claim, status="unknown")
    values = _answer_numbers(claim)
    value_matches = any(_close(value, expected) for value in values)
    dimensions_match = _answer_dimensions_match(
        rendered,
        answer_unit=str(plan.get("answer_unit") or ""),
        answer_scale=str(plan.get("answer_scale") or ""),
    )
    if value_matches and dimensions_match:
        return CalculationClaimResult(
            claim=claim,
            status="supported",
            supporting_evidence_ids=matched_ids,
        )
    return CalculationClaimResult(
        claim=claim,
        status="contradicted",
        contradicting_evidence_ids=matched_ids,
    )


def _result_claim(claims: list[str], rendered: str, expected: Decimal) -> str:
    for claim in claims:
        if any(_close(value, expected) for value in _answer_numbers(claim)):
            return claim
    numeric_claim = next((claim for claim in claims if _answer_numbers(claim)), "")
    return numeric_claim or (claims[0] if len(claims) == 1 else rendered.strip())


def _answer_numbers(value: str) -> list[Decimal]:
    numbers: list[Decimal] = []
    for raw in _NUMBER_RE.findall(str(value or "")):
        normalized = raw.replace(",", "").replace(" ", "")
        negative = normalized.startswith("(") and normalized.endswith(")")
        normalized = normalized.strip("()$€£¥")
        try:
            parsed = Decimal(normalized)
        except InvalidOperation:
            continue
        if parsed == parsed.to_integral() and 1900 <= parsed <= 2100:
            continue
        numbers.append(-parsed if negative else parsed)
    return numbers


def _answer_dimensions_match(
    answer: str,
    *,
    answer_unit: str,
    answer_scale: str,
) -> bool:
    lowered = str(answer or "").lower()
    expected_unit = answer_unit.strip().lower()
    expected_scale = answer_scale.strip().lower()
    if expected_unit in {"percent", "%"} and not (
        "%" in lowered or "percent" in lowered
    ):
        return False
    if expected_scale in _SCALE_TERMS and expected_scale not in lowered:
        return False
    conflicting_scales = (_SCALE_TERMS - {expected_scale}) & set(lowered.split())
    return not conflicting_scales


def _decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _close(left: Decimal, right: Decimal) -> bool:
    tolerance = max(Decimal("0.005"), abs(right) * Decimal("0.0001"))
    return abs(left - right) <= tolerance
