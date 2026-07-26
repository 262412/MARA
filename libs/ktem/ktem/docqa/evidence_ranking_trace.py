from __future__ import annotations


def ranking_trace(
    *,
    candidate_limit: int,
    input_count: int,
    output_count: int,
) -> dict[str, object]:
    return {
        "candidate_stage": "post_fusion",
        "candidate_limit": candidate_limit,
        "candidate_input_count": input_count,
        "output_count": output_count,
        "backend_execution": "not_recorded",
    }
