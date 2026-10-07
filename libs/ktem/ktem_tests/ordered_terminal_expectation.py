"""Apply the runtime migration's explicit ordering contract to frozen baselines.

Historical fixture bytes and their source revisions stay unchanged. Only the
formerly set-ordered evidence projections, diagnostics and derived hash change;
the full observation, including answers and citation order, is still compared.
"""

from copy import deepcopy

from ktem_contracts.terminal_semantic_commit import projection_hash


def ordered_terminal_expectation(observation):
    expected = deepcopy(observation)
    state = expected["terminal_state"]
    metadata = state["evidence_bundle"]["metadata"]
    for name in ("verified_evidence", "verified_claim_support_evidence"):
        if name in metadata:
            metadata[name].sort(key=lambda item: item["canonical_id"])
    trace = metadata.get("evidence_selection_trace", {})
    if "trace_validation_errors" in trace:
        trace["trace_validation_errors"].sort()
    commit = state["terminal_semantic_commit"]
    commit["authoritative_evidence"].sort(key=lambda item: item["canonical_id"])
    unsigned = {key: value for key, value in commit.items() if key != "projection_hash"}
    commit["projection_hash"] = projection_hash(_restore_tuples(unsigned))
    return expected


def _restore_tuples(value):
    if isinstance(value, dict):
        if set(value) == {"__tuple__"}:
            return tuple(_restore_tuples(item) for item in value["__tuple__"])
        return {key: _restore_tuples(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_restore_tuples(item) for item in value]
    return value
