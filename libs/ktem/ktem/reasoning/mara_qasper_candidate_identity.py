from __future__ import annotations

import hashlib
import json
from typing import Any

from ktem.docqa.query_planning import request_planning_question


def candidate_transaction_identity(
    request: Any,
    route: str,
    seed: int,
) -> dict[str, str]:
    context = dict(getattr(request, "trace_context", {}) or {})
    group_id = str(context.get("trace_group_id") or "")
    benchmark_route_id = str(
        context.get("benchmark_route_id")
        or getattr(request, "benchmark_route_id", "")
        or ""
    )
    if not group_id:
        group_id = candidate_digest(
            {
                "contract_id": "benchmark_transaction_identity.v1",
                "dataset": str(getattr(request, "dataset_family", "") or ""),
                "question": request_planning_question(request),
            }
        )
    transaction_id = candidate_digest(
        {
            "trace_group_id": group_id,
            "benchmark_route_id": benchmark_route_id,
            "route": route,
            "stage": "candidate_generation",
            "seed": seed,
        }
    )
    return {
        "trace_group_id": group_id,
        "benchmark_route_id": benchmark_route_id,
        "internal_route": route,
        "transaction_id": transaction_id,
        "attempt_id": f"{transaction_id}:candidate_generation:1",
    }


def effective_candidate_seed(request: Any, *, default_seed: int) -> int:
    value = getattr(request, "generation_seed", None)
    return default_seed if value is None else int(value)


def candidate_model_name(llm: Any | None) -> str:
    if llm is None:
        return ""
    for key in ("model_name", "model", "model_id"):
        value = str(getattr(llm, key, "") or "").strip()
        if value:
            return value
    return f"{type(llm).__module__}.{type(llm).__name__}"


def candidate_digest(value: Any) -> str:
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
