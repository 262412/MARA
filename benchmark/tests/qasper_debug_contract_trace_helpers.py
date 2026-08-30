from __future__ import annotations

import json
from typing import Any

from benchmark.tests.contract_smoke_fixtures import _fixture_digest


def debug_generator_trace(
    example_id: str,
    route: str,
    group_id: str,
    candidate: str,
    *,
    plan_candidate_decisions_digest: str,
) -> dict[str, Any]:
    transaction_id = f"generator:{example_id}:{route}"
    raw_response = json.dumps(
        {"candidate": candidate}, ensure_ascii=False, separators=(",", ":")
    )
    raw_digest = _fixture_digest(raw_response)
    candidate_digest = _fixture_digest(candidate)
    context = _generator_decision_context(
        candidate,
        plan_candidate_decisions_digest,
    )
    canonical_decisions = _canonical_selector_decisions()
    output_digest = _generator_output_digest(
        candidate,
        raw_digest,
        candidate_digest,
    )
    return {
        **_generator_header(
            candidate,
            raw_response,
            raw_digest,
            candidate_digest,
        ),
        **_generator_projections(context, canonical_decisions, raw_digest),
        **_debug_generator_lineage(
            candidate,
            raw_response,
            raw_digest,
            candidate_digest,
            output_digest,
            transaction_id,
        ),
        "trace_group_id": group_id,
        "transaction_id": transaction_id,
        "attempt_id": f"{transaction_id}:1",
        "effective_seed": 20260724,
        "input_digest": _fixture_digest({"generator-input": route}),
        "output_digest": output_digest,
    }


def _generator_decision_context(
    candidate: str,
    plan_candidate_decisions_digest: str,
) -> dict[str, Any]:
    return {
        "typed_candidate": candidate,
        "required_slot_count": 1,
        "legal_plan_count": 1,
        "plan_candidate_decisions_digest": plan_candidate_decisions_digest,
        "decision_plan_alignment": (
            "conflicts_with_legal_local_plan"
            if candidate == "unanswerable"
            else "locally_plan_eligible"
        ),
    }


def _generator_output_digest(
    candidate: str,
    raw_digest: str,
    candidate_digest: str,
) -> str:
    return _fixture_digest(
        {
            "raw_response_digest": raw_digest,
            "provider_output_digest": raw_digest,
            "cleaned_response_digest": raw_digest,
            "raw_candidate": candidate,
            "raw_candidate_digest": candidate_digest,
            "typed_candidate": candidate,
            "typed_candidate_digest": candidate_digest,
            "raw_candidate_identity_preserved": True,
            "status": "parsed",
            "failure_reason": "",
            "finish_reason": "stop",
        }
    )


def _generator_header(
    candidate: str,
    raw_response: str,
    raw_digest: str,
    candidate_digest: str,
) -> dict[str, Any]:
    return {
        "contract_id": "qasper_typed_candidate_generation.v2",
        "status": "parsed",
        "model": "Qwen/Qwen3-8B",
        "message_stack": [
            {"index": 0, "role": "system", "content": "verify"},
            {"index": 1, "role": "user", "content": "question"},
        ],
        "raw_response": raw_response,
        "raw_response_digest": raw_digest,
        "provider_output_digest": raw_digest,
        "raw_response_truncated": False,
        "cleaned_response": raw_response,
        "raw_candidate": candidate,
        "raw_candidate_failure_reason": "",
        "raw_candidate_digest": candidate_digest,
        "typed_candidate": candidate,
        "typed_candidate_digest": candidate_digest,
        "raw_candidate_identity_preserved": True,
        "typed_proposition": {
            "actor": "current_paper",
            "predicate": "use",
            "object_surface": "the method",
            "quantifier": "none",
        },
        "question_proposition_resolution": {"status": "complete"},
        "required_slots": [
            {
                "slot_id": "support:boolean_proposition",
                "binding_status": "bound",
                "evidence_ids": ["span:paper:s1"],
                "evidence_refs": ["E1:S1"],
            }
        ],
        "finish_reason": "stop",
        "failure_reason": "",
    }


def _generator_projections(
    context: dict[str, Any],
    canonical_decisions: list[dict[str, Any]],
    raw_digest: str,
) -> dict[str, Any]:
    return {
        "candidate_prompt_projection_trace": debug_record_projection(
            "qasper_candidate_prompt_projection.v1",
            decision="selected_for_candidate_prompt",
        ),
        "candidate_request_projection_trace": debug_record_projection(
            "qasper_candidate_request_projection.v1",
            decision="selected_for_model_request",
        ),
        "canonical_selector_projection_trace": {
            "contract_id": "qasper_canonical_selector_projection.v1",
            "complete": True,
            "input_record_count": 1,
            "output_record_count": 1,
            "input_selector_count": 1,
            "selected_selector_count": 1,
            "decision_count": 1,
            "decisions_digest": _fixture_digest(canonical_decisions),
            "decisions": canonical_decisions,
        },
        "model_decision": {
            "contract_id": "qasper_model_candidate_decision.v1",
            "status": "parsed",
            "decision": context["typed_candidate"],
            "decision_origin": "model_output",
            "rationale_status": "not_requested_by_low_entropy_contract",
            "decision_context": context,
            "decision_context_digest": _fixture_digest(context),
            "raw_response_digest": raw_digest,
        },
    }


def _canonical_selector_decisions() -> list[dict[str, Any]]:
    return [
        {
            "record_index": 1,
            "source_selector_index": 1,
            "evidence_id": "span:paper:s1",
            "selector_ref": "E1:S1",
            "decision": "selected",
            "reason": "selected_for_canonical_selector_universe",
        }
    ]


def debug_record_projection(contract_id: str, *, decision: str) -> dict[str, Any]:
    decisions = [
        {
            "evidence_id": "span:paper:s1",
            "selected": True,
            "decision": decision,
        }
    ]
    attempts = [
        {
            "record_ids": ["span:paper:s1"],
            "decision": "accepted",
        }
    ]
    return {
        "contract_id": contract_id,
        "complete": True,
        "input_record_count": 1,
        "selected_record_count": 1,
        "decision_count": 1,
        "decisions_digest": _fixture_digest(decisions),
        "decisions": decisions,
        "attempt_count": 1,
        "attempts_digest": _fixture_digest(attempts),
        "attempts": attempts,
    }


def _debug_generator_lineage(
    candidate: str,
    raw_response: str,
    raw_digest: str,
    candidate_digest: str,
    output_digest: str,
    transaction_id: str,
) -> dict[str, Any]:
    return {
        "transformation_stages": [
            {
                "stage": "raw_response",
                "value": raw_response,
                "digest": raw_digest,
                "failure_reason": "",
            },
            {
                "stage": "cleaning",
                "value": raw_response,
                "digest": raw_digest,
                "changed": False,
                "failure_reason": "",
            },
            {
                "stage": "typed_candidate",
                "value": candidate,
                "digest": candidate_digest,
                "failure_reason": "",
                "source_stage": "cleaning",
                "identity_preserved": True,
            },
        ],
        "attempts": [
            {
                "attempt_id": f"{transaction_id}:1",
                "status": "parsed",
                "failure_reason": "",
                "raw_response": raw_response,
                "cleaned_response": raw_response,
                "raw_candidate": candidate,
                "raw_candidate_digest": candidate_digest,
                "typed_candidate": candidate,
                "typed_candidate_digest": candidate_digest,
                "raw_candidate_identity_preserved": True,
                "finish_reason": "stop",
                "output_digest": output_digest,
            }
        ],
    }
