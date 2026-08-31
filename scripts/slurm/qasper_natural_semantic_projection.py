from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from benchmark.qasper_causal_evidence_chain_utils import canonical_digest


def frozen_projection_complete(
    value: Mapping[str, Any],
    *,
    contract_id: str,
    input_count_key: str,
    attempts_required: bool,
) -> bool:
    trace = dict(value)
    decisions = list(trace.get("decisions") or [])
    attempts = list(trace.get("attempts") or [])
    attempts_complete = bool(
        not attempts_required
        or (
            attempts
            and int(trace.get("attempt_count") or 0) == len(attempts)
            and canonical_digest(attempts) == trace.get("attempts_digest")
        )
    )
    return bool(
        trace.get("contract_id") == contract_id
        and trace.get("complete") is True
        and int(trace.get(input_count_key) or 0) == len(decisions)
        and int(trace.get("decision_count") or 0) == len(decisions)
        and canonical_digest(decisions) == trace.get("decisions_digest")
        and attempts_complete
    )
