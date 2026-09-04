from __future__ import annotations

import hashlib
import json
from time import monotonic

import ktem.docqa.execution as execution_module
import pytest
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.execution import (
    ABSTAIN_MESSAGE,
    deadline_exhausted_controller_result,
    execute_controller_turn,
)
from ktem.docqa.route_budget import RouteDeadlineExhausted
from ktem.docqa.terminal_semantic_commit import (
    build_terminal_semantic_commit,
    terminal_commit_outcome,
    terminal_commit_projection_present,
)


def _request() -> DocQARequest:
    return DocQARequest(
        prompt="Which input does the method use?",
        retrieval_query="method input",
        task_type="free_text",
        verification_mode="strict",
        verification_domain="qasper",
        route_policy="doc",
        allowed_routes=["doc_text"],
        selected_file_ids=["paper"],
        origin="benchmark",
    )


def _supported_projection() -> tuple[dict, dict, dict]:
    return (
        {
            "mode": "strict",
            "status": "supported",
            "reason": "Direct support.",
            "action": "generate",
            "verified_citations": ["evidence-1"],
        },
        {"status": "ok", "action": "return", "reason": "verified"},
        {
            "metadata": {
                "verified_claim_support_evidence": [
                    {"evidence_id": "evidence-1", "quote": "Direct support."}
                ]
            }
        },
    )


def _rehash(commit: dict) -> None:
    unsigned = {key: value for key, value in commit.items() if key != "projection_hash"}
    commit["projection_hash"] = hashlib.sha256(
        json.dumps(
            unsigned,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
    ).hexdigest()


@pytest.mark.parametrize(
    ("answer", "verify", "guardrail", "bundle", "expected_hash"),
    [
        (
            "The method uses direct evidence.",
            {
                "mode": "strict",
                "status": "supported",
                "reason": "Direct support.",
                "action": "generate",
                "verified_citations": ["evidence-1"],
            },
            {"status": "ok", "action": "return", "reason": "verified"},
            {
                "metadata": {
                    "verified_claim_support_evidence": [
                        {"evidence_id": "evidence-1", "quote": "Direct support."}
                    ]
                }
            },
            "14bb35422ce7d64d918174fc2d56151da8b15dd367d579cce28c4800249ea734",
        ),
        (
            ABSTAIN_MESSAGE,
            {
                "mode": "strict",
                "status": "unknown",
                "reason": "No exact support.",
                "action": "abstain",
                "verified_citations": [],
            },
            {"status": "unknown", "action": "abstain", "reason": "Fail closed."},
            {"metadata": {}},
            "60d7b4a42f83f259d3cab1d332f93344403cdf78fbe506dda1a7cc9456c69ce1",
        ),
    ],
)
def test_a1_normal_projection_hashes_remain_byte_equivalent(
    answer: str,
    verify: dict,
    guardrail: dict,
    bundle: dict,
    expected_hash: str,
) -> None:
    commit = build_terminal_semantic_commit(answer, verify, guardrail, bundle).as_dict()

    assert commit["projection_hash"] == expected_hash
    assert terminal_commit_projection_present(commit)


@pytest.mark.parametrize(
    "outcome",
    ["execution_failed", "timeout", "cancelled"],
)
def test_operational_outcomes_never_publish_semantic_authority(outcome: str) -> None:
    verify, guardrail, bundle = _supported_projection()
    commit = build_terminal_semantic_commit(
        ABSTAIN_MESSAGE,
        verify,
        guardrail,
        bundle,
        outcome=outcome,
        outcome_reason=f"{outcome}_reason",
    ).as_dict()

    assert commit["outcome"] == outcome
    assert commit["answer_status"] == "abstained"
    assert commit["semantic_answer"] == "unanswerable"
    assert commit["authoritative_evidence"] == []
    assert commit["citations"] == []
    assert terminal_commit_projection_present(commit)
    assert terminal_commit_outcome(commit) == outcome


def test_rehashed_operational_authority_is_rejected() -> None:
    commit = build_terminal_semantic_commit(
        ABSTAIN_MESSAGE,
        {"status": "timeout", "action": "error"},
        {"status": "timeout", "action": "error"},
        {"metadata": {}},
        outcome="timeout",
        outcome_reason="route_deadline_exhausted",
    ).as_dict()
    commit["authoritative_evidence"] = [{"evidence_id": "stale"}]
    commit["citations"] = ["stale"]
    _rehash(commit)

    assert not terminal_commit_projection_present(commit)
    assert terminal_commit_outcome(commit) == ""


def test_route_deadline_projects_timeout_not_safe_abstention() -> None:
    request = _request()
    now = monotonic()
    result = deadline_exhausted_controller_result(
        request,
        RouteDeadlineExhausted(
            blocking_stage="retrieval",
            absolute_deadline_monotonic=now,
            call_timeout_budget_seconds=0.1,
            remaining_route_seconds=0.0,
        ),
    )

    commit = result.engine_terminal_commit
    assert commit["outcome"] == "timeout"
    assert commit["outcome_reason"] == "route_deadline_exhausted"
    assert commit["semantic_answer"] == "unanswerable"
    assert commit["presentation_answer"] == ABSTAIN_MESSAGE
    assert terminal_commit_projection_present(commit)


@pytest.mark.parametrize("failure_stage", ["planning", "retrieval", "generation"])
def test_operational_exception_returns_one_execution_failed_result(
    monkeypatch: pytest.MonkeyPatch,
    failure_stage: str,
) -> None:
    request = _request()
    if failure_stage == "planning":
        monkeypatch.setattr(
            execution_module,
            "_planned_execution",
            lambda *_args: (_ for _ in ()).throw(RuntimeError("planner failed")),
        )

    def retrieve(*_args):
        if failure_stage == "retrieval":
            raise RuntimeError("backend failed")
        return {
            "evidence": [
                {
                    "evidence_id": "input",
                    "source_id": "paper",
                    "text": "The method uses labeled features.",
                }
            ]
        }

    def generate(*_args):
        if failure_stage == "generation":
            raise RuntimeError("backend failed")
        return "The method uses labeled features."

    result = execute_controller_turn(request, retrieve=retrieve, generate=generate)

    commit = result.engine_terminal_commit
    expected_reason = (
        "planning_failed" if failure_stage == "planning" else "backend_failed"
    )
    assert commit["outcome"] == "execution_failed"
    assert commit["outcome_reason"] == expected_reason
    assert commit["semantic_answer"] == "unanswerable"
    assert commit["presentation_answer"] == ABSTAIN_MESSAGE
    assert commit["authoritative_evidence"] == []
    assert commit["citations"] == []
    assert result.guardrail_decision.action == "error"
    assert any(
        event.get("stage") == "terminal_outcome"
        and event.get("outcome") == "execution_failed"
        for event in result.controller_trace
    )
    assert terminal_commit_projection_present(commit)


def test_operational_outcome_fixture_is_closed_and_mutually_exclusive() -> None:
    commits = [
        build_terminal_semantic_commit(
            ABSTAIN_MESSAGE,
            {"status": outcome, "action": "error"},
            {"status": outcome, "action": "error"},
            {"metadata": {}},
            outcome=outcome,
            outcome_reason=f"{outcome}_reason",
        ).as_dict()
        for outcome in ("execution_failed", "timeout", "cancelled")
    ]

    assert {terminal_commit_outcome(commit) for commit in commits} == {
        "execution_failed",
        "timeout",
        "cancelled",
    }
    assert all(commit["outcome"] != "safe_abstention" for commit in commits)
