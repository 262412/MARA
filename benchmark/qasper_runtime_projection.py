from __future__ import annotations

import hashlib
import json
from typing import Any

from ktem.docqa.terminal_semantic_commit import terminal_commit_projection_present

from .qasper_answer_normalization import canonical_semantic_label


def runtime_projection_present(prediction: dict[str, Any]) -> bool:
    state = prediction.get("engine_terminal_state")
    verify_decision = prediction.get("engine_verify_decision")
    guardrail_decision = prediction.get("engine_terminal_guardrail_decision")
    evidence_bundle = prediction.get("engine_terminal_evidence_bundle")
    terminal_answer = str(prediction.get("engine_terminal_answer") or "")
    if not (
        terminal_answer
        and isinstance(state, dict)
        and state.get("contract_id") == "engine_terminal_state.v1"
        and isinstance(verify_decision, dict)
        and isinstance(guardrail_decision, dict)
        and isinstance(evidence_bundle, dict)
    ):
        return False
    if not _projection_fields_match(
        state,
        terminal_answer=terminal_answer,
        verify_decision=verify_decision,
        guardrail_decision=guardrail_decision,
        evidence_bundle=evidence_bundle,
    ):
        return False
    commit = prediction.get("engine_terminal_commit") or prediction.get(
        "terminal_semantic_commit"
    )
    if commit is not None and commit != {}:
        if not terminal_commit_projection_present(commit):
            return False
        state_commit = state.get("terminal_semantic_commit")
        if isinstance(state_commit, dict) and state_commit != commit:
            return False
        if (
            commit.get("semantic_answer") != terminal_answer
            or commit.get("verify_decision") != verify_decision
            or commit.get("guardrail_decision") != guardrail_decision
        ):
            return False
    expected_hash = hashlib.sha256(
        json.dumps(
            state,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()
    return str(prediction.get("engine_terminal_projection_hash") or "") == (
        expected_hash
    )


def runtime_terminal_commit(prediction: dict[str, Any]) -> dict[str, Any]:
    commit = prediction.get("engine_terminal_commit") or prediction.get(
        "terminal_semantic_commit"
    )
    return dict(commit) if isinstance(commit, dict) else {}


def typed_boolean_authority_frame_complete(
    payload: dict[str, Any],
    *,
    expected_polarity: str,
    evidence_id: str,
    require_exact: bool = False,
) -> bool:
    predicate = str(payload.get("predicate") or payload.get("relation") or "")
    object_identity = str(payload.get("object") or "")
    arguments = payload.get("arguments") or payload.get("predicate_arguments") or ()
    arguments = [str(value) for value in arguments]
    polarity = str(payload.get("canonical_answer_polarity") or "")
    scope = str(payload.get("scope") or payload.get("section_scope") or "")
    start = payload.get("authoritative_span_start")
    end = payload.get("authoritative_span_end")
    return bool(
        (not require_exact or payload.get("authority_status") == "exact")
        and payload.get("actor") == "current_paper"
        and predicate
        and object_identity
        and arguments == [object_identity]
        and polarity == expected_polarity
        and str(payload.get("qualifier") or "")
        and str(payload.get("quantifier") or "")
        and scope
        and scope not in {"future_work", "related_work"}
        and str(payload.get("authoritative_evidence_id") or "") == evidence_id
        and str(payload.get("authoritative_evidence_ref") or "")
        and str(payload.get("authoritative_quote") or "")
        and isinstance(start, int)
        and isinstance(end, int)
        and start >= 0
        and end > start
    )


def _projection_fields_match(
    state: dict[str, Any],
    *,
    terminal_answer: str,
    verify_decision: dict[str, Any],
    guardrail_decision: dict[str, Any],
    evidence_bundle: dict[str, Any],
) -> bool:
    raw_answer = str(state.get("raw_generated_answer") or "")
    raw_candidate_label = _candidate_label(raw_answer, evidence_bundle)
    verified_label = str(verify_decision.get("canonical_answer_polarity") or "")
    conflict_terminal = verify_decision.get("status") == "verified_conflict"
    correction_applied = bool(
        verify_decision.get("semantic_correction_applied")
        or (
            verified_label in {"yes", "no"}
            and _candidate_label(raw_answer, evidence_bundle) != verified_label
        )
    )
    expected = {
        "answer": terminal_answer,
        "raw_generated_answer": raw_answer,
        "raw_candidate_label": raw_candidate_label,
        "normalized_candidate_label": (
            _candidate_label(terminal_answer, evidence_bundle)
            if conflict_terminal
            else raw_candidate_label
        ),
        "verified_canonical_answer": verified_label,
        "semantic_correction_applied": correction_applied,
        "correction_reason": (
            str(verify_decision.get("reason") or "") if correction_applied else ""
        ),
        "authoritative_evidence_id": str(
            verify_decision.get("authoritative_evidence_id") or ""
        ),
        "authoritative_evidence_ref": str(
            verify_decision.get("authoritative_evidence_ref") or ""
        ),
        "authoritative_quote": str(verify_decision.get("authoritative_quote") or ""),
        "authoritative_conflict": verify_decision.get("authoritative_conflict") or {},
        "terminal_reason": (
            str(verify_decision.get("reason") or "") if conflict_terminal else ""
        ),
        "guardrail_result": guardrail_decision,
        "verify_decision": verify_decision,
        "guardrail_decision": guardrail_decision,
        "evidence_bundle": evidence_bundle,
    }
    return all(state.get(key) == value for key, value in expected.items())


def _candidate_label(answer: str, evidence_bundle: dict[str, Any]) -> str:
    label = canonical_semantic_label(answer)
    if label in {"yes", "no", "unanswerable"}:
        return label
    metadata = evidence_bundle.get("metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    plan = metadata.get("query_plan") or metadata.get("bound_query_plan")
    answer_type = str(plan.get("answer_type") or "") if isinstance(plan, dict) else ""
    return "invalid" if answer_type.lower() in {"boolean", "unanswerable"} else ""
