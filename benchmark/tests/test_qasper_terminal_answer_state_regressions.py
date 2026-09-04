from __future__ import annotations

from typing import Any

import pytest

from benchmark.terminal_answer_state import rebuild_terminal_answer_state


def _supported_decision(answer: str) -> dict[str, Any]:
    return {
        "mode": "strict",
        "status": "supported",
        "action": "return",
        "claims": [answer],
        "unsupported_claims": [],
        "unknown_claims": [],
        "verified_citations": ["evidence:paper:support"],
        "claim_results": [
            {
                "claim_id": "claim:terminal",
                "claim": answer,
                "status": "supported",
                "supporting_evidence_ids": ["evidence:paper:support"],
                "contradicting_evidence_ids": [],
            }
        ],
    }


def _support() -> dict[str, str]:
    return {
        "evidence_id": "support",
        "source_id": "paper",
        "text": "The current paper reports the supported result.",
    }


def test_terminal_answer_rewrite_rebuilds_all_answer_dependent_state() -> None:
    prediction: dict[str, Any] = {
        "predicted_answer": "unanswerable",
        "answer_for_user": "unanswerable",
        "answer_for_scoring": "unanswerable",
        "answer_status": "abstained",
        "verify_decision": {"status": "not_enough_evidence", "action": "abstain"},
        "guardrail_decision": {
            "status": "not_enough_evidence",
            "action": "abstain",
        },
        "evidence_metadata": {"answer_dependent_state": "legacy"},
    }
    decision = _supported_decision("yes")

    terminal = rebuild_terminal_answer_state(
        prediction,
        answer="yes",
        verify_decision=decision,
        supporting_evidence=[_support()],
        guardrail_decision={"status": "ok", "action": "return"},
        emitted_citations=[
            {"kind": "evidence", "evidence_id": "evidence:paper:support"}
        ],
    )

    assert prediction["predicted_answer"] == "yes"
    assert prediction["answer_for_scoring"] == "yes"
    assert prediction["answer_status"] == "answered"
    assert prediction["verify_decision"] == decision
    assert prediction["evidence_metadata"]["verify_decision"] == decision
    assert prediction["evidence_metadata"]["answer_dependent_state"] == (
        "terminal_answer_state.v1"
    )
    assert terminal == prediction["terminal_answer_state"]


def test_second_finalization_is_idempotent() -> None:
    prediction: dict[str, Any] = {"evidence_metadata": {}}
    decision = _supported_decision("yes")
    kwargs: dict[str, Any] = {
        "answer": "yes",
        "verify_decision": decision,
        "supporting_evidence": [_support()],
        "guardrail_decision": {"status": "ok", "action": "return"},
        "emitted_citations": [],
    }

    first = rebuild_terminal_answer_state(prediction, **kwargs)
    second = rebuild_terminal_answer_state(prediction, **kwargs)

    assert second == first
    assert second["state_version"] == 1


def test_citation_rendering_does_not_change_terminal_answer_identity() -> None:
    prediction: dict[str, Any] = {
        "answer_for_user": "yes paper#page:3",
        "answer_for_scoring": "yes",
        "structured_citations": [
            {"kind": "page", "source_id": "paper", "page_label": "3"}
        ],
        "evidence_metadata": {},
    }

    terminal = rebuild_terminal_answer_state(
        prediction,
        answer="yes",
        verify_decision=_supported_decision("yes"),
        supporting_evidence=[_support()],
        guardrail_decision={"status": "ok", "action": "return"},
        emitted_citations=prediction["structured_citations"],
    )

    assert prediction["answer_for_user"] == "yes paper#page:3"
    assert terminal["answer"] == "yes"
    assert prediction["answer_for_scoring"] == terminal["answer"]


def test_abstention_to_answer_recovery_clears_old_guardrail() -> None:
    prediction: dict[str, Any] = {
        "guardrail_decision": {
            "status": "not_enough_evidence",
            "action": "abstain",
        },
        "evidence_metadata": {
            "guardrail_decision": {
                "status": "not_enough_evidence",
                "action": "abstain",
            }
        },
    }

    rebuild_terminal_answer_state(
        prediction,
        answer="no",
        verify_decision=_supported_decision("no"),
        supporting_evidence=[_support()],
        guardrail_decision={"status": "ok", "action": "return"},
        emitted_citations=[],
    )

    assert prediction["guardrail_decision"]["action"] == "return"
    assert prediction["evidence_metadata"]["guardrail_decision"]["action"] == ("return")


def test_answer_to_abstention_rebuilds_verifier_and_citations() -> None:
    prediction: dict[str, Any] = {
        "predicted_answer": "yes",
        "structured_citations": [{"source_id": "paper", "page_label": "3"}],
        "predicted_citations": ["paper#page:3"],
        "evidence_metadata": {
            "verified_claim_support_evidence": [_support()],
            "emitted_citation_evidence": [_support()],
        },
    }
    decision = {
        "mode": "strict",
        "status": "not_enough_evidence",
        "action": "abstain",
        "claims": [],
        "unsupported_claims": [],
        "unknown_claims": [],
        "verified_citations": [],
        "claim_results": [],
    }

    terminal = rebuild_terminal_answer_state(
        prediction,
        answer="unanswerable",
        verify_decision=decision,
        supporting_evidence=[],
        guardrail_decision={
            "status": "not_enough_evidence",
            "action": "abstain",
        },
        emitted_citations=[],
    )

    assert prediction["answer_status"] == "abstained"
    assert prediction["structured_citations"] == []
    assert prediction["predicted_citations"] == []
    assert prediction["evidence_metadata"]["verified_claim_support_evidence"] == []
    assert terminal["verify_decision"]["status"] == "not_enough_evidence"


def test_terminal_state_matches_final_scoring_answer() -> None:
    prediction: dict[str, Any] = {
        "answer_for_user": "no paper#page:4",
        "evidence_metadata": {},
    }

    terminal = rebuild_terminal_answer_state(
        prediction,
        answer="no",
        verify_decision=_supported_decision("no"),
        supporting_evidence=[_support()],
        guardrail_decision={"status": "ok", "action": "return"},
        emitted_citations=[],
    )

    assert terminal["answer"] == prediction["answer_for_scoring"]
    assert terminal["answer_status"] == prediction["answer_status"]


_FOCUSED_STALE_STATE_FIXTURES: list[tuple[str, str]] = [
    ("unanswerable", "supported free-text answer"),
    ("unanswerable", "short supported answer"),
    ("unanswerable", "multi-sentence supported answer"),
    ("unanswerable", "supported numeric description"),
    ("unanswerable", "supported comparison"),
    ("unanswerable", "supported style description"),
    ("unanswerable", "supported method description"),
    ("unanswerable", "supported benchmark description"),
    ("unanswerable", "supported challenge result"),
    ("unanswerable", "supported disciplinary claim"),
    ("unanswerable", "supported state-of-the-art description"),
    ("yes", "yes with unsupported extension"),
    ("unanswerable", "supported assistant description"),
    ("unanswerable", "supported task result"),
]


@pytest.mark.parametrize(
    ("final_answer", "stale_answer"), _FOCUSED_STALE_STATE_FIXTURES
)
def test_focused_stale_state_fixture_rebuilds_authoritative_answer(
    final_answer: str,
    stale_answer: str,
) -> None:
    prediction: dict[str, Any] = {
        "answer_for_scoring": final_answer,
        "post_contract_verification": {
            "answer": stale_answer,
            "verify_decision": _supported_decision(stale_answer),
        },
        "evidence_metadata": {},
    }
    abstained = final_answer == "unanswerable"
    decision = (
        {
            "mode": "strict",
            "status": "not_enough_evidence",
            "action": "abstain",
            "claims": [],
            "unsupported_claims": [],
            "unknown_claims": [],
            "verified_citations": [],
            "claim_results": [],
        }
        if abstained
        else _supported_decision(final_answer)
    )

    terminal = rebuild_terminal_answer_state(
        prediction,
        answer=final_answer,
        verify_decision=decision,
        supporting_evidence=[] if abstained else [_support()],
        guardrail_decision={
            "status": "not_enough_evidence" if abstained else "ok",
            "action": "abstain" if abstained else "return",
        },
        emitted_citations=[],
    )

    assert terminal["answer"] == final_answer
    assert prediction["post_contract_verification"]["answer"] == final_answer
