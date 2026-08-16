from __future__ import annotations

from copy import deepcopy

from ktem_contracts.conformance import TERMINAL_COMMIT_CONFORMANCE_VECTORS
from ktem_contracts.terminal_semantic_commit import (
    build_operational_terminal_commit,
    terminal_commit_outcome,
    terminal_commit_projection_present,
)


def test_canonical_terminal_commit_vectors_are_strict_and_stable() -> None:
    for vector in TERMINAL_COMMIT_CONFORMANCE_VECTORS:
        commit = deepcopy(vector["commit"])
        assert terminal_commit_projection_present(commit)
        assert terminal_commit_outcome(commit) == vector["outcome"]

        commit["semantic_answer"] = "tampered"
        assert not terminal_commit_projection_present(commit)


def test_operational_builder_matches_the_canonical_timeout_vector() -> None:
    timeout = next(
        vector
        for vector in TERMINAL_COMMIT_CONFORMANCE_VECTORS
        if vector["name"] == "timeout_v3"
    )

    assert (
        build_operational_terminal_commit(
            outcome="timeout",
            reason="route_timeout",
            presentation_answer="Partial answer",
        )
        == timeout["commit"]
    )
