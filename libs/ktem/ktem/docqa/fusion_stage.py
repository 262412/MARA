from __future__ import annotations

from typing import Any

from .evidence_identity import identity_of

FUSION_STAGE_CONTRACT = "fusion_stage_snapshot.v1"
FUSION_STAGE_STATES = frozenset({"executed", "passthrough", "not_executed"})


def fusion_stage_snapshot(
    route: str,
    input_items: list[dict[str, Any]],
    output_items: list[dict[str, Any]],
    *,
    fusion_trace: dict[str, Any] | None,
) -> dict[str, Any]:
    """Record the candidate transition at the fusion boundary.

    A non-hybrid route is a deliberate pass-through, not a post-fusion stage.
    An empty candidate set means that fusion did not execute.  Hybrid routes
    carry the actual fusion trace and are therefore marked executed even when
    the trace produced no candidates; the validator can then apply the normal
    answerability requirements to that empty output.
    """

    input_identities = [identity_of(item).key for item in input_items]
    output_identities = [identity_of(item).key for item in output_items]
    if fusion_trace is not None:
        state = "executed"
        candidate_stage = "post_fusion"
        reason = "hybrid_fusion_executed"
    elif input_items or output_items:
        state = "passthrough"
        candidate_stage = "fusion_passthrough"
        reason = "route_does_not_use_cross_modal_fusion"
    else:
        state = "not_executed"
        candidate_stage = "fusion_not_executed"
        reason = "no_fusion_candidates"
    return {
        "contract_id": FUSION_STAGE_CONTRACT,
        "route": str(route or ""),
        "state": state,
        "candidate_stage": candidate_stage,
        "reason": reason,
        "input_count": len(input_items),
        "output_count": len(output_items),
        "input_identities": input_identities,
        "output_identities": output_identities,
        "identity_preserved": input_identities == output_identities,
        "fusion_trace_present": fusion_trace is not None,
    }
