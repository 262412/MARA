from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from .boolean_authority_schema import (
    ARGUMENT_CONJUNCTION_RULE,
    SEMANTIC_EVIDENCE_SET_RULE,
)
from .boolean_proposition_compatibility import boolean_argument_token_coverage
from .boolean_scope_quantifiers import _closed_quantifier
from .query_plan_schema import QueryPlan, with_plan_id

_COMPARISON_RE = re.compile(
    r"\b(?:compare|comparison|versus|vs\.?|between|difference|relative\s+to|than)\b",
    flags=re.IGNORECASE,
)
_DEPENDENT_BINDING_RE = re.compile(
    r"\b(?:same|single|respectively|together|before|after|without|except|neither|either)\b",
    flags=re.IGNORECASE,
)
_COORDINATED_ACTION_RE = re.compile(
    r"\band\s+(?:analy[sz]e|apply|compare|conduct|design|develop|evaluate|"
    r"introduce|measure|offer|perform|present|propose|release|report|test|train|"
    r"use|vot)\w*\b",
    flags=re.IGNORECASE,
)


def boolean_conjunction_spec(question: str) -> dict[str, Any] | None:
    """Return the static proof obligation for a safe Boolean argument conjunction."""

    value = str(question or "").strip()
    quantifier = _closed_quantifier(value)
    if (
        not re.search(r"\b(?:and|both)\b", value, re.IGNORECASE)
        or re.search(r"\bor\b", value, re.IGNORECASE)
        or _COMPARISON_RE.search(value)
        or _DEPENDENT_BINDING_RE.search(value)
        or _COORDINATED_ACTION_RE.search(value)
        or quantifier not in {"none", "both"}
    ):
        return None
    required, _covered = boolean_argument_token_coverage(value, value)
    if len(required) < 2:
        return None
    return {
        "operator": "all",
        "premise_mode": "all_required",
        "semantics": "open_world",
        "rule_id": ARGUMENT_CONJUNCTION_RULE,
        "quantifier": quantifier,
        "required_argument_tokens": list(required),
        "max_premises": 4,
    }


def with_boolean_support_group(plan: QueryPlan, question: str) -> QueryPlan:
    """Attach the static conjunction obligation to an external Boolean plan."""

    if plan.answer_type != "boolean":
        return plan
    conjunction = boolean_conjunction_spec(question)
    if conjunction is None:
        return plan
    constraints = dict(plan.constraints)
    if constraints.get("boolean_support_group") == conjunction:
        return plan
    constraints["boolean_support_group"] = conjunction
    return with_plan_id(replace(plan, constraints=constraints), question)


def derivation_support_group_constraint(
    derivation: dict[str, Any],
    existing: Any,
) -> dict[str, Any]:
    """Project a verified runtime derivation into the QueryPlan interface."""

    existing = existing if isinstance(existing, dict) else {}
    premise_refs = [
        str(value).strip()
        for value in derivation.get("premise_refs") or ()
        if str(value).strip()
    ]
    try:
        existing_max = int(existing.get("max_premises") or 0)
    except (TypeError, ValueError):
        existing_max = 0
    conclusion = derivation.get("conclusion")
    conclusion = conclusion if isinstance(conclusion, dict) else {}
    projected = {
        "operator": "all",
        "premise_mode": "all_required",
        "semantics": "open_world",
        "rule_id": str(derivation.get("rule_id") or ""),
        "quantifier": str(conclusion.get("quantifier") or ""),
        "required_argument_tokens": list(
            derivation.get("required_argument_tokens") or []
        ),
        "max_premises": max(existing_max, len(premise_refs)),
    }
    if str(derivation.get("rule_id") or "") == SEMANTIC_EVIDENCE_SET_RULE:
        attestation = derivation.get("verifier_attestation")
        attestation = attestation if isinstance(attestation, dict) else {}
        projected.update(
            {
                "support_mode": str(derivation.get("support_mode") or ""),
                "distinctness_basis": "evidence_ref",
                "verifier_contract_id": str(attestation.get("contract_id") or ""),
                "verdict_contract_id": str(
                    attestation.get("verdict_contract_id") or ""
                ),
            }
        )
    return projected
