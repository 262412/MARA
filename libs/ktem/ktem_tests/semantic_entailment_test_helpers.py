from __future__ import annotations

from typing import Any

from ktem.docqa.semantic_entailment_audit import semantic_entailment_audit_attestation


def audited_verdict(
    response: dict[str, Any],
    question: str,
) -> dict[str, Any]:
    """Attach a valid independent-audit attestation to a semantic test verdict."""

    response["entailment_audit"] = semantic_entailment_audit_attestation(
        question,
        response["verdict"],
        response["premises"],
        model="independent-test-auditor",
        seed=8,
    )
    return response
