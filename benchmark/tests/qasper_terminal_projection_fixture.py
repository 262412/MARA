from __future__ import annotations

from copy import deepcopy
from typing import Any

from ktem.docqa.engine_terminal_projection import engine_terminal_projection
from ktem.docqa.evidence_schema import EvidenceBundle
from ktem.docqa.execution_models import GuardrailDecision
from ktem.docqa.verification import VerifyDecision


def attach_valid_terminal_projection(
    prediction: dict[str, Any],
    *,
    answer: str = "yes",
) -> dict[str, Any]:
    bundle_value = prediction.get("evidence_bundle") or {}
    bundle = EvidenceBundle(
        route=str(prediction.get("route") or "text_rag"),
        items=deepcopy(bundle_value.get("items") or []),
        metadata=deepcopy(prediction.get("evidence_metadata") or {}),
    )
    verify = VerifyDecision(
        mode="strict",
        status="verified",
        reason="",
        action="generate",
        canonical_answer_polarity=answer,
    )
    guardrail = GuardrailDecision(status="ok", action="return", reason="")
    (
        terminal_answer,
        state,
        terminal_verify,
        terminal_guardrail,
        terminal_bundle,
        projection_hash,
    ) = engine_terminal_projection(answer, verify, guardrail, bundle)
    commit = state["terminal_semantic_commit"]
    prediction.update(
        predicted_answer=terminal_answer,
        answer_for_scoring=terminal_answer,
        answer_status=commit["answer_status"],
        terminal_outcome=commit["outcome"],
        engine_terminal_answer=terminal_answer,
        engine_terminal_state=state,
        engine_verify_decision=terminal_verify,
        engine_terminal_guardrail_decision=terminal_guardrail,
        engine_terminal_evidence_bundle=terminal_bundle,
        engine_terminal_projection_hash=projection_hash,
        engine_terminal_commit=commit,
        terminal_semantic_commit=commit,
    )
    return prediction
