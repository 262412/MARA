"""Real candidate preparation/regeneration and verifier, with a fixed model reply."""

from copy import deepcopy

import pytest
from ktem.docqa.execution import _configured_verify, execute_controller_turn
from ktem.docqa.terminal_semantic_commit import terminal_commit_projection_present
from ktem_tests.test_docqa_qasper_pre_audit_terminalization import _candidate_generator
from ktem_tests.test_docqa_recovery_state_machine import (
    EXACT_AUTHORITY,
    NEAR_MATCH,
    _evidence,
    _request,
)


@pytest.mark.parametrize("improves", [False, True])
def test_qasper_regenerates_and_reverifies_only_after_real_pack_progress(improves):
    request = _request(route_policy="doc")
    generate_candidate = _candidate_generator("yes")
    actual_verify = _configured_verify(None, None)
    calls, candidates = [], []

    def retrieve(current, decision):
        calls.append(("retrieve", current.retrieval_round_id))
        assert decision.legacy_route == "doc_text"
        text = (
            EXACT_AUTHORITY
            if improves and current.retrieval_round_id == 2
            else NEAR_MATCH
        )
        identity = f"r{current.retrieval_round_id}" if improves else "same"
        return {"evidence": [_evidence(identity, text)]}

    def generate(current, decision, bundle):
        calls.append(
            ("generate", bundle.metadata.get("qasper_candidate_generation_sequence", 0))
        )
        answer = generate_candidate(current, decision, bundle)
        candidates.append(deepcopy(bundle.metadata["qasper_candidate_generation"]))
        return answer

    def verify(*args):
        calls.append(("verify", args[-1]))
        return actual_verify(*args)

    result = execute_controller_turn(
        request, retrieve=retrieve, generate=generate, verify=verify
    )
    assert calls == [
        ("retrieve", 1),
        ("generate", 0),
        ("verify", "yes"),
        ("retrieve", 2),
    ] + ([("generate", 1), ("verify", "yes")] if improves else [])
    assert result.engine_terminal_commit["outcome"] == (
        "answered" if improves else "safe_abstention"
    )
    assert terminal_commit_projection_present(result.engine_terminal_commit)
    assert candidates[0]["generation_sequence"] == 0
    if improves:
        assert candidates[1]["generation_sequence"] == 1
        assert (
            candidates[1]["predecessor_transaction_id"]
            == candidates[0]["transaction_id"]
        )
        assert candidates[1]["transaction_id"] != candidates[0]["transaction_id"]
        assert (
            candidates[1]["canonical_semantic_pack_digest"]
            != candidates[0]["canonical_semantic_pack_digest"]
        )
        assert result.verify_decision.verified_citations == ["evidence:paper:r2"]
        assert candidates[1]["raw_candidate"] == "yes"
        assert result.engine_terminal_commit["semantic_answer"] == "yes"
    else:
        assert len(candidates) == 1
        assert result.controller_trace[-1]["stop_reason"] == "recovery_no_progress"
        assert result.verify_decision.verified_citations == []
