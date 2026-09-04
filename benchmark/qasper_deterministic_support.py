from __future__ import annotations

from typing import Any


def deterministic_support_ids(trace: dict[str, Any]) -> set[str]:
    bound_ids = trace.get("final_support_evidence_ids") or []
    values = bound_ids if isinstance(bound_ids, list) else str(bound_ids).split(",")
    output = {str(value).strip() for value in values if str(value).strip()}
    authoritative_id = str(trace.get("authoritative_quote_evidence_id") or "").strip()
    if authoritative_id:
        output.add(authoritative_id)
    if output:
        return output
    if str(trace.get("raw_verifier_verdict") or "") != "deterministic_scope":
        return set()
    if str(trace.get("quote_grounded") or "").lower() != "true":
        return set()
    raw_ids = trace.get("verifier_input_evidence_ids") or []
    values = raw_ids if isinstance(raw_ids, list) else str(raw_ids).split(",")
    return {str(value).strip() for value in values if str(value).strip()}
