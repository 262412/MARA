"""Real retrieval loops install narrow context and restore it on every exit."""

from types import SimpleNamespace
from typing import Any

import pytest
from ktem.docqa import retrieval_rounds
from ktem.docqa.query_plan_schema import EvidenceSlot, QueryPlan


@pytest.mark.parametrize("round_id", [1, 2, 3])
@pytest.mark.parametrize("metadata_kind", ["missing", "none", "dict"])
@pytest.mark.parametrize("fails", [False, True])
def test_query_slot_round_and_metadata_restore_after_success_or_error(
    round_id, metadata_kind, fails
):
    request = SimpleNamespace(
        retrieval_query="original",
        retrieval_slot_id="original-slot",
        retrieval_round_id=8,
    )
    original: Any = None if metadata_kind == "none" else {"nested": []}
    if metadata_kind != "missing":
        request.retrieval_query_metadata = original
    calls = []
    error = LookupError("retriever failure")

    def retrieve(current, decision):
        assert decision == "decision"
        calls.append(
            (
                current.retrieval_query,
                current.retrieval_slot_id,
                current.retrieval_round_id,
                dict(current.retrieval_query_metadata),
            )
        )
        if fails:
            raise error
        return {}

    def invoke():
        if round_id == 1:
            plan = QueryPlan(
                "extractive",
                "lookup",
                evidence_slots=(
                    EvidenceSlot("a", "support", query="query-a"),
                    EvidenceSlot("b", "support", query="query-b"),
                ),
            )
            return retrieval_rounds._retrieve_first_round(
                request, "decision", retrieve, plan
            )
        return retrieval_rounds._retrieve_second_round(
            request,
            "decision",
            retrieve,
            [
                {"query_id": "id-a", "slot_id": "a", "query": "query-a"},
                {"query_id": "id-b", "slot_id": "b", "query": "query-b"},
            ],
            round_id=round_id,
        )

    if fails:
        with pytest.raises(LookupError) as caught:
            invoke()
        assert caught.value is error
    else:
        invoke()
    kind = "initial" if round_id == 1 else "recovery"
    metadata = {
        "contract_id": "initial_retrieval_query.v1"
        if round_id == 1
        else "recovery_query.v1",
        "query_kind": kind,
    }
    expected = [
        ("query-a", "a", round_id, metadata),
        ("query-b", "b", round_id, metadata),
    ]
    assert calls == expected[:1] if fails else calls == expected
    assert (
        request.retrieval_query,
        request.retrieval_slot_id,
        request.retrieval_round_id,
    ) == ("original", "original-slot", 8)
    if metadata_kind == "missing":
        assert not hasattr(request, "retrieval_query_metadata")
    else:
        assert request.retrieval_query_metadata is original
