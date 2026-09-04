from __future__ import annotations

from typing import Any

from ktem.docqa.engine_terminal_projection import engine_terminal_projection
from ktem.docqa.evidence import EvidenceBundle
from ktem.docqa.execution_contracts import ABSTAIN_MESSAGE
from ktem.docqa.execution_models import GuardrailDecision
from ktem.docqa.verification import VerifyDecision


def operational_terminal_fields(
    *,
    outcome: str,
    reason: str,
) -> dict[str, Any]:
    verify = VerifyDecision(
        mode="off",
        status=outcome,
        reason=reason,
        action="error",
    )
    guardrail = GuardrailDecision(
        status=outcome,
        action="error",
        reason=reason,
    )
    (
        terminal_answer,
        terminal_state,
        terminal_verify,
        terminal_guardrail,
        terminal_evidence,
        projection_hash,
    ) = engine_terminal_projection(
        ABSTAIN_MESSAGE,
        verify,
        guardrail,
        EvidenceBundle(route="benchmark_runtime", items=[], metadata={}),
        terminal_outcome=outcome,
        terminal_outcome_reason=reason,
    )
    commit = dict(terminal_state["terminal_semantic_commit"])
    return {
        "engine_terminal_answer": terminal_answer,
        "engine_terminal_state": terminal_state,
        "engine_verify_decision": terminal_verify,
        "engine_terminal_guardrail_decision": terminal_guardrail,
        "engine_terminal_evidence_bundle": terminal_evidence,
        "engine_terminal_projection_hash": projection_hash,
        "engine_terminal_commit": commit,
        "terminal_semantic_commit": commit,
        "terminal_outcome": commit["outcome"],
        "terminal_outcome_reason": commit["outcome_reason"],
    }
