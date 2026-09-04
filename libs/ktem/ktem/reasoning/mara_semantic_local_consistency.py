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
    literal_disagreement_refs: list[str] = []
    semantic_denial_fields = _semantic_denial_fields(audit)
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
        literal_disagreement = bool(
            fragment_in_quote and auditor_fragment_entailed is False
        )
        if literal_disagreement:
            literal_disagreement_refs.append(premise_ref)
        elif auditor_fragment_entailed is False:
            semantic_denial_fields.append(f"{premise_ref}.fragment_entailed")
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
                "literal_fragment_disagreement": literal_disagreement,
                "internally_inconsistent": False,
            }
        )
    semantic_denial_fields = list(dict.fromkeys(semantic_denial_fields))
    override_eligible = bool(literal_disagreement_refs and not semantic_denial_fields)
    inconsistent_refs = literal_disagreement_refs if override_eligible else []
    for check in checks:
        check["internally_inconsistent"] = bool(
            override_eligible and check["premise_ref"] in literal_disagreement_refs
        )
    status, disagreement_scope = _consistency_disposition(
        override_eligible=override_eligible,
        semantic_denial_fields=semantic_denial_fields,
    )
    return {
        "contract_id": DETERMINISTIC_LOCAL_PREMISE_CONSISTENCY_CONTRACT,
        "status": status,
        "method": "nfkc_casefold_whitespace_exact_substring",
        "independent_from_models": True,
        "disagreement_scope": disagreement_scope,
        "override_eligible": override_eligible,
        "literal_disagreement_premise_refs": literal_disagreement_refs,
        "semantic_denial_fields": semantic_denial_fields,
        "inconsistent_premise_refs": inconsistent_refs,
        "checks": checks,
    }


def _consistency_disposition(
    *,
    override_eligible: bool,
    semantic_denial_fields: Sequence[str],
) -> tuple[str, str]:
    if override_eligible:
        return "auditor_internal_inconsistency", "literal_fragment_only"
    if semantic_denial_fields:
        return "auditor_semantic_rejection", "semantic"
    return "consistent", "none"


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
        diagnostics["local_premise_consistency"] = consistency
    return consistency


def _semantic_denial_fields(audit: Mapping[str, Any]) -> list[str]:
    denied: list[str] = []
    for index, check in enumerate(audit.get("premise_checks") or [], start=1):
        if not isinstance(check, Mapping):
            denied.append(f"P{index}.premise_check")
            continue
        premise_ref = str(check.get("premise_ref") or f"P{index}")
        for field in (
            "scope_consistent",
            "proposition_bindings_valid",
            "evidence_relation_valid",
        ):
            if check.get(field) is not True:
                denied.append(f"{premise_ref}.{field}")
        for slot_check in check.get("proposition_slot_checks") or []:
            if not isinstance(slot_check, Mapping):
                denied.append(f"{premise_ref}.proposition_slot_checks")
            elif slot_check.get("binding_valid") is not True:
                slot = str(slot_check.get("slot") or "unknown")
                denied.append(f"{premise_ref}.slot:{slot}.binding_valid")
    for field in ("jointly_entails", "each_premise_required", "contradiction_free"):
        if audit.get(field) is not True:
            denied.append(field)
    conclusion = audit.get("conclusion_check")
    if not isinstance(conclusion, Mapping):
        denied.append("conclusion_check")
    else:
        for field in (
            "conclusion_entailed",
            "actor_consistent",
            "predicate_consistent",
            "object_consistent",
            "polarity_consistent",
            "quantifier_consistent",
            "scope_consistent",
        ):
            if conclusion.get(field) is not True:
                denied.append(f"conclusion_check.{field}")
    return denied


def _normalize_exact_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(normalized.split())


def _text_digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
