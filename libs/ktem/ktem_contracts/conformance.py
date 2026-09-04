from __future__ import annotations

from typing import Any

TERMINAL_COMMIT_CONFORMANCE_VECTORS: tuple[dict[str, Any], ...] = (
    {
        "name": "answered_v3",
        "outcome": "answered",
        "commit": {
            "answer_status": "answered",
            "authoritative_evidence": [],
            "citations": [],
            "contract_id": "terminal_semantic_commit.v3",
            "guardrail_decision": {"action": "return", "status": "ok"},
            "outcome": "answered",
            "outcome_reason": "",
            "presentation_answer": "Grounded answer",
            "projection_hash": (
                "9dcc3342280813687b9b99bb68d62ee6457bfdf59377eaefc74c0bc8df4a3c72"
            ),
            "semantic_answer": "Grounded answer",
            "state_version": 3,
            "verify_decision": {"action": "return", "status": "supported"},
        },
    },
    {
        "name": "timeout_v3",
        "outcome": "timeout",
        "commit": {
            "answer_status": "abstained",
            "authoritative_evidence": [],
            "citations": [],
            "contract_id": "terminal_semantic_commit.v3",
            "guardrail_decision": {
                "action": "error",
                "reason": "route_timeout",
                "status": "timeout",
            },
            "outcome": "timeout",
            "outcome_reason": "route_timeout",
            "presentation_answer": "Partial answer",
            "projection_hash": (
                "edd35a8166ea46dfb608d4e279d5751ec2a22528346c6dbd39447e193c702b3b"
            ),
            "semantic_answer": "unanswerable",
            "state_version": 3,
            "verify_decision": {
                "action": "error",
                "reason": "route_timeout",
                "status": "timeout",
            },
        },
    },
    {
        "name": "safe_abstention_v2",
        "outcome": "safe_abstention",
        "commit": {
            "answer_status": "abstained",
            "authoritative_evidence": [],
            "citations": [],
            "contract_id": "terminal_semantic_commit.v2",
            "guardrail_decision": {"action": "abstain"},
            "projection_hash": (
                "27b45210cc2df1225da504150dca897d0f6d8700489edfa04b4dc5d88951c1b6"
            ),
            "semantic_answer": "unanswerable",
            "state_version": 2,
            "verify_decision": {"status": "not_enough_evidence"},
        },
    },
)
