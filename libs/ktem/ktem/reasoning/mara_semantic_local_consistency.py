from __future__ import annotations

import hashlib
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

DETERMINISTIC_LOCAL_PREMISE_CONSISTENCY_CONTRACT = (
    "deterministic_local_premise_consistency.v1"
)


def deterministic_local_premise_consistency(
    premises: Sequence[Mapping[str, Any]],
    audit: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Check model premise judgments against exact normalized selector text.

    This check only establishes that a proposed fragment is literally present in
    its bound quote. It never establishes scope or joint conclusion entailment.
    """

    audit = audit if isinstance(audit, Mapping) else {}
    raw_checks = audit.get("premise_checks")
    checks_by_ref = {
        str(check.get("premise_ref") or ""): check
        for check in raw_checks or []
        if isinstance(check, Mapping)
    }
    checks: list[dict[str, Any]] = []
    inconsistent_refs: list[str] = []
    for index, premise in enumerate(premises, start=1):
        premise_ref = f"P{index}"
        model_check = checks_by_ref.get(premise_ref, {})
        quote = str(premise.get("quote") or "")
        fragment = str(premise.get("proposition_fragment") or "")
        normalized_quote = _normalize_exact_text(quote)
        normalized_fragment = _normalize_exact_text(fragment)
        fragment_in_quote = bool(
            normalized_fragment and normalized_fragment in normalized_quote
        )
        auditor_fragment_entailed = model_check.get("fragment_entailed")
        inconsistent = bool(fragment_in_quote and auditor_fragment_entailed is False)
        if inconsistent:
            inconsistent_refs.append(premise_ref)
        checks.append(
            {
                "premise_ref": premise_ref,
                "quote_digest": _text_digest(quote),
                "fragment_digest": _text_digest(fragment),
                "fragment_quote_relation": (
                    "exact_normalized_substring"
                    if fragment_in_quote
                    else "not_exact_normalized_substring"
                ),
                "auditor_fragment_entailed": auditor_fragment_entailed,
                "auditor_scope_consistent": model_check.get("scope_consistent"),
                "internally_inconsistent": inconsistent,
            }
        )
    return {
        "contract_id": DETERMINISTIC_LOCAL_PREMISE_CONSISTENCY_CONTRACT,
        "status": (
            "auditor_internal_inconsistency" if inconsistent_refs else "consistent"
        ),
        "method": "nfkc_casefold_whitespace_exact_substring",
        "independent_from_models": True,
        "inconsistent_premise_refs": inconsistent_refs,
        "checks": checks,
    }


def record_local_premise_consistency(
    diagnostics: dict[str, Any],
    premises: Sequence[Mapping[str, Any]],
    audit: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Persist a local check without allowing it to verify the conclusion."""

    if audit is None:
        return {}
    consistency = deterministic_local_premise_consistency(premises, audit)
    diagnostics.setdefault("local_premise_consistency_history", []).append(consistency)
    if consistency["status"] == "auditor_internal_inconsistency":
        diagnostics["auditor_internal_inconsistency"] = True
        diagnostics["auditor_internal_inconsistency_count"] = (
            int(diagnostics.get("auditor_internal_inconsistency_count") or 0) + 1
        )
        diagnostics["local_premise_consistency"] = consistency
    else:
        diagnostics.setdefault("auditor_internal_inconsistency", False)
        diagnostics.setdefault("auditor_internal_inconsistency_count", 0)
        diagnostics.setdefault("local_premise_consistency", consistency)
    return consistency


def _normalize_exact_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(normalized.split())


def _text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
