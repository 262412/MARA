from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

from .boolean_claim_verification import canonical_boolean_answer_polarity
from .evidence import EvidenceBundle
from .execution_contracts import ABSTAIN_MESSAGE, ENGINE_TERMINAL_STATE_CONTRACT
from .execution_models import GuardrailDecision
from .verification import VerifyDecision


def engine_terminal_projection(
    answer: str,
    verify_decision: VerifyDecision,
    guardrail_decision: GuardrailDecision,
    bundle: EvidenceBundle,
    *,
    raw_generated_answer: str | None = None,
) -> tuple[str, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any], str]:
    terminal_answer = str(answer or "")
    raw_answer = (
        terminal_answer if raw_generated_answer is None else str(raw_generated_answer)
    )
    terminal_verify = deepcopy(verify_decision.as_dict())
    terminal_guardrail = deepcopy(guardrail_decision.as_dict())
    terminal_evidence = deepcopy(bundle.as_dict())
    raw_candidate_label = normalized_candidate_label(raw_answer, terminal_evidence)
    conflict_terminal = terminal_verify.get("status") == "verified_conflict"
    candidate_label = (
        normalized_candidate_label(terminal_answer, terminal_evidence)
        if conflict_terminal
        else raw_candidate_label
    )
    verified_label = str(terminal_verify.get("canonical_answer_polarity") or "").strip()
    correction_applied = bool(
        terminal_verify.get("semantic_correction_applied")
        or (verified_label in {"yes", "no"} and candidate_label != verified_label)
    )
    terminal_state = {
        "contract_id": ENGINE_TERMINAL_STATE_CONTRACT,
        "answer": terminal_answer,
        "raw_generated_answer": raw_answer,
        "raw_candidate_label": raw_candidate_label,
        "normalized_candidate_label": candidate_label,
        "verified_canonical_answer": verified_label,
        "semantic_correction_applied": correction_applied,
        "correction_reason": (
            str(terminal_verify.get("reason") or "") if correction_applied else ""
        ),
        "authoritative_evidence_id": str(
            terminal_verify.get("authoritative_evidence_id") or ""
        ),
        "authoritative_evidence_ref": str(
            terminal_verify.get("authoritative_evidence_ref") or ""
        ),
        "authoritative_quote": str(terminal_verify.get("authoritative_quote") or ""),
        "authoritative_conflict": deepcopy(
            terminal_verify.get("authoritative_conflict") or {}
        ),
        "terminal_reason": (
            str(terminal_verify.get("reason") or "") if conflict_terminal else ""
        ),
        "guardrail_result": deepcopy(terminal_guardrail),
        "verify_decision": deepcopy(terminal_verify),
        "guardrail_decision": deepcopy(terminal_guardrail),
        "evidence_bundle": deepcopy(terminal_evidence),
    }
    projection_hash = hashlib.sha256(
        json.dumps(
            terminal_state,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    return (
        terminal_answer,
        terminal_state,
        terminal_verify,
        terminal_guardrail,
        terminal_evidence,
        projection_hash,
    )


def normalized_candidate_label(
    answer: str,
    evidence_bundle: dict[str, Any],
) -> str:
    polarity = canonical_boolean_answer_polarity(answer)
    if polarity:
        return polarity
    normalized = " ".join(str(answer or "").strip().lower().split())
    if normalized.startswith(
        (
            "unanswerable",
            "unknown",
            "insufficient evidence",
            "not enough evidence",
            "unable to answer",
            "cannot answer",
            ABSTAIN_MESSAGE.lower(),
        )
    ):
        return "unanswerable"
    metadata = evidence_bundle.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    plan = metadata.get("query_plan") or metadata.get("bound_query_plan")
    answer_type = str(plan.get("answer_type") or "") if isinstance(plan, dict) else ""
    return "invalid" if answer_type.lower() in {"boolean", "unanswerable"} else ""
