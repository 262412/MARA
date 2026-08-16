from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any

TERMINAL_SEMANTIC_COMMIT_CONTRACT = "terminal_semantic_commit.v3"
LEGACY_TERMINAL_SEMANTIC_COMMIT_CONTRACT = "terminal_semantic_commit.v2"
TERMINAL_OUTCOMES = frozenset(
    {
        "answered",
        "safe_abstention",
        "execution_failed",
        "timeout",
        "cancelled",
    }
)
OPERATIONAL_TERMINAL_OUTCOMES = frozenset({"execution_failed", "timeout", "cancelled"})

_V2_FIELDS = frozenset(
    {
        "contract_id",
        "semantic_answer",
        "answer_status",
        "verify_decision",
        "guardrail_decision",
        "authoritative_evidence",
        "citations",
        "projection_hash",
        "state_version",
    }
)
_V3_FIELDS = _V2_FIELDS | {
    "presentation_answer",
    "outcome",
    "outcome_reason",
}


def _commit_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            payload,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


projection_hash = _commit_hash


def with_projection_hash(payload: dict[str, Any]) -> dict[str, Any]:
    commit = deepcopy(payload)
    commit.pop("projection_hash", None)
    commit["projection_hash"] = _commit_hash(commit)
    return commit


def build_operational_terminal_commit(
    *,
    outcome: str,
    reason: str,
    presentation_answer: str,
) -> dict[str, Any]:
    normalized_outcome = str(outcome).strip().lower()
    if normalized_outcome not in OPERATIONAL_TERMINAL_OUTCOMES:
        raise ValueError(f"Unsupported operational terminal outcome: {outcome}")
    normalized_reason = str(reason)
    action = "cancel" if normalized_outcome == "cancelled" else "error"
    decision = {
        "status": normalized_outcome,
        "action": action,
        "reason": normalized_reason,
    }
    return with_projection_hash(
        {
            "contract_id": TERMINAL_SEMANTIC_COMMIT_CONTRACT,
            "semantic_answer": "unanswerable",
            "presentation_answer": str(presentation_answer),
            "outcome": normalized_outcome,
            "outcome_reason": normalized_reason,
            "answer_status": "abstained",
            "verify_decision": dict(decision),
            "guardrail_decision": dict(decision),
            "authoritative_evidence": [],
            "citations": [],
            "state_version": 3,
        }
    )


def terminal_commit_projection_present(commit: Any) -> bool:
    if not isinstance(commit, dict):
        return False
    contract_id = commit.get("contract_id")
    if contract_id == TERMINAL_SEMANTIC_COMMIT_CONTRACT:
        if not _valid_v3_projection(commit):
            return False
    elif contract_id == LEGACY_TERMINAL_SEMANTIC_COMMIT_CONTRACT:
        if not _valid_v2_projection(commit):
            return False
    else:
        return False
    expected = dict(commit)
    projection_hash = expected.pop("projection_hash", None)
    if not _valid_projection_hash(projection_hash):
        return False
    computed = _commit_hash(expected)
    return computed == projection_hash


def terminal_commit_outcome(commit: Any) -> str:
    if not terminal_commit_projection_present(commit):
        return ""
    if commit["contract_id"] == TERMINAL_SEMANTIC_COMMIT_CONTRACT:
        return str(commit["outcome"])
    return "answered" if commit["answer_status"] == "answered" else "safe_abstention"


def _valid_v2_projection(commit: dict[str, Any]) -> bool:
    return bool(
        set(commit) == _V2_FIELDS
        and commit.get("state_version") == 2
        and commit.get("answer_status") in {"answered", "abstained"}
        and _valid_projection_values(commit)
    )


def _valid_v3_projection(commit: dict[str, Any]) -> bool:
    outcome = commit.get("outcome")
    expected_status = "answered" if outcome == "answered" else "abstained"
    return bool(
        set(commit) == _V3_FIELDS
        and commit.get("state_version") == 3
        and isinstance(outcome, str)
        and outcome in TERMINAL_OUTCOMES
        and commit.get("answer_status") == expected_status
        and outcome_matches_semantic(outcome, commit.get("semantic_answer"))
        and isinstance(commit.get("presentation_answer"), str)
        and isinstance(commit.get("outcome_reason"), str)
        and _valid_projection_values(commit)
        and _valid_outcome_authority(outcome, commit)
    )


def _valid_projection_values(commit: dict[str, Any]) -> bool:
    evidence = commit.get("authoritative_evidence")
    citations = commit.get("citations")
    return bool(
        isinstance(commit.get("semantic_answer"), str)
        and isinstance(commit.get("verify_decision"), dict)
        and isinstance(commit.get("guardrail_decision"), dict)
        and isinstance(evidence, list)
        and all(isinstance(item, dict) for item in evidence)
        and isinstance(citations, list)
        and all(isinstance(item, str) for item in citations)
    )


def _valid_outcome_authority(outcome: str, commit: dict[str, Any]) -> bool:
    if outcome not in OPERATIONAL_TERMINAL_OUTCOMES:
        return True
    return not commit["authoritative_evidence"] and not commit["citations"]


def _valid_projection_hash(value: Any) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def outcome_matches_semantic(outcome: str, semantic_answer: Any) -> bool:
    is_abstention = semantic_answer == "unanswerable"
    return is_abstention if outcome != "answered" else not is_abstention
