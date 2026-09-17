"""Fixed backend boundaries around real planning, binding, budget and recovery."""

import copy
import json
import os
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import patch

from ktem.docqa import (
    evidence,
    execution,
    pipeline_stage_timings,
    route_budget,
    selection_assessment_snapshot,
)
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.query_planning import retrieval_budget
from ktem.docqa.retrieval_rounds import retrieve_for_verifier_recovery
from ktem.docqa.terminal_semantic_commit import terminal_commit_projection_present
from ktem_tests.test_docqa_recovery_state_machine import (
    EXACT_AUTHORITY,
    NEAR_MATCH,
    QUESTION,
    _evidence,
)

SEAMS = (
    "retrieval_commits_last",
    "retrieval_exhausted",
    "retrieval_budget_stop",
    "verifier_first_candidate_only",
    "verifier_third_round",
    "same_route_recovery",
    "typed_authority_ready",
    "verification_budget_stop",
    "generation_failed",
    "retrieval_failed",
    "deadline_before_call",
)


def observe_in_fixed_process():
    completed = subprocess.run(
        [sys.executable, "-B", "-m", "ktem_tests.route_closeout_seams"],
        env={
            **os.environ,
            "PYTHONHASHSEED": "0",
            "PYTHONPATH": os.pathsep.join(sys.path),
        },
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=60,
    )
    return json.loads(completed.stdout)


def _request(name):
    traversal = name.startswith("retrieval_") and name != "retrieval_failed"
    question = "What does the document say?" if traversal else QUESTION
    request = DocQARequest(
        prompt=question,
        retrieval_query=question,
        task_type="free_text" if traversal else "boolean",
        verification_mode="strict",
        verification_domain="general" if traversal else "qasper",
        route_policy="doc" if traversal or name == "same_route_recovery" else "auto",
        allowed_routes=["doc_text", "hybrid", "graph_global"],
        selected_file_ids=["paper"],
        origin="benchmark",
        route_deadline_monotonic=200,
        route_timeout_seconds=100,
    )
    if name == "deadline_before_call":
        request.route_deadline_monotonic = 100
    request.retrieval_slot_id = "original-slot"
    request.retrieval_round_id = 9
    return request


def _retrieve_payload(name, current, decision, clock):
    if name == "retrieval_failed":
        raise LookupError("fixed retrieval failure")
    if name.startswith("retrieval_"):
        if name == "retrieval_budget_stop" and decision.legacy_route == "hybrid":
            clock[0] = 180
        if name == "retrieval_commits_last" and decision.legacy_route == "graph_global":
            return {
                "graph_evidence": [
                    {
                        "id": "graph-answer",
                        "label": "Graph answer",
                        "summary": "The graph evidence answers the question.",
                        "source_ids": ["paper"],
                    }
                ]
            }
        return {}
    round_id = current.retrieval_round_id
    text = NEAR_MATCH
    if name in {"typed_authority_ready", "generation_failed"}:
        text = EXACT_AUTHORITY
    elif name in {"same_route_recovery", "verifier_third_round"}:
        text = {
            1: "The paper introduces a conversational system."
            if name == "verifier_third_round"
            else NEAR_MATCH,
            2: NEAR_MATCH if name == "verifier_third_round" else EXACT_AUTHORITY,
            3: EXACT_AUTHORITY,
        }[round_id]
    return {"evidence": [_evidence(f"round-{round_id}", text)]}


def observe_seam(name):
    request, clock, calls = _request(name), [100.0], []
    original_metadata = {"owner": ["original"]}
    request.retrieval_query_metadata = original_metadata
    original = (
        request.retrieval_query,
        request.retrieval_slot_id,
        request.retrieval_round_id,
    )

    def retrieve(current, decision):
        calls.append(
            {
                "stage": "retrieve",
                "route": decision.legacy_route,
                "query": current.retrieval_query,
                "slot": current.retrieval_slot_id,
                "round": current.retrieval_round_id,
                "metadata": copy.deepcopy(current.retrieval_query_metadata),
                "budget": retrieval_budget(current.query_plan),
            }
        )
        return _retrieve_payload(name, current, decision, clock)

    def generate(current, decision, bundle):
        calls.append({"stage": "generate", "route": decision.legacy_route})
        if name == "generation_failed":
            raise ValueError("fixed generation failure")
        if name == "verification_budget_stop":
            clock[0] = 177
        return (
            "The graph evidence answers the question."
            if name.startswith("retrieval_")
            else "yes"
        )

    actual_verify = execution._configured_verify(None, None)

    def verify(*args):
        calls.append({"stage": "verify", "answer": args[-1]})
        return actual_verify(*args)

    with patch.object(
        pipeline_stage_timings, "perf_counter", lambda: 100
    ), patch.object(
        evidence, "time", SimpleNamespace(perf_counter=lambda: 100)
    ), patch.object(
        selection_assessment_snapshot, "time", SimpleNamespace(perf_counter=lambda: 100)
    ), patch.object(
        route_budget, "monotonic", lambda: clock[0]
    ), patch.object(
        route_budget, "_signal_timeout_available", lambda: False
    ):
        result = execution.execute_controller_turn(
            request, retrieve=retrieve, generate=generate, verify=verify
        )
        repeated = None
        if name == "verifier_third_round":
            repeated = retrieve_for_verifier_recovery(
                request,
                result.controller_decision,
                retrieve,
                result.evidence_bundle,
                evaluate=lambda *_a, **_k: None,
                retry_reason="already used",
            )
            assert repeated is None
    return _observation(request, result, calls, original, original_metadata, repeated)


def _observation(request, result, calls, original, original_metadata, repeated):
    assert original == (
        request.retrieval_query,
        request.retrieval_slot_id,
        request.retrieval_round_id,
    )
    assert request.retrieval_query_metadata is original_metadata
    assert original_metadata == {"owner": ["original"]}
    assert terminal_commit_projection_present(result.engine_terminal_commit)
    return {
        "calls": calls,
        "planned": request.planned_query_plan.as_dict(),
        "plan": request.query_plan.as_dict(),
        "plan_id": request.query_plan_id,
        "version": request.query_plan_state_version,
        "result": result.as_dict(),
        "request_budget_trace": request.route_budget_trace,
        "restored": list(original),
        "repeat_focused_result": repeated,
    }


if __name__ == "__main__":
    print(json.dumps({name: observe_seam(name) for name in SEAMS}, ensure_ascii=False))
