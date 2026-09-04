from __future__ import annotations

from copy import deepcopy
from typing import Any

import ktem.docqa.boolean_authority_schema as authority_schema
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.boolean_proposition_evidence import boolean_proposition_binding_trace
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.execution import ABSTAIN_MESSAGE, execute_controller_turn


def _evidence(
    evidence_id: str,
    text: str,
    *,
    page_label: str = "1",
    canonical_start: int | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "page_label": page_label,
        "section_id": "results",
        "text": text,
    }
    if canonical_start is not None:
        item["canonical_start"] = canonical_start
    return item


def _run_boolean(
    question: str,
    answer: str,
    items: list[dict[str, Any]],
):
    return execute_controller_turn(
        DocQARequest(
            prompt=question,
            retrieval_query=question,
            task_type="boolean",
            verification_mode="strict",
            verification_domain="qasper",
            route_policy="doc",
            allowed_routes=["doc_text"],
            selected_file_ids=["paper"],
            origin="benchmark",
        ),
        retrieve=lambda *_args: {"evidence": items},
        generate=lambda *_args: answer,
    )


def _candidate_for_quote(trace: dict[str, Any], quote: str) -> dict[str, Any]:
    return next(
        candidate
        for candidate in trace["proposition_candidates"]
        if candidate["quote"] == quote
    )


def test_boolean_authority_states_are_one_closed_schema() -> None:
    assert authority_schema.BOOLEAN_AUTHORITY_STATES == (
        "missing",
        "retrieved_unverified",
        "verified_support",
        "verified_conflict",
    )


def test_retrieved_candidate_trace_records_typed_frame_and_exact_span() -> None:
    question = "Did the authors use the clinical corpus?"
    quote = "We used the clinical corpus."
    text = f"Setup details. {quote} Additional analysis followed."
    item = _evidence("support", text, canonical_start=700)
    evidence_id = identity_of(item).key
    local_start = text.index(quote)
    local_end = local_start + len(quote)

    trace = boolean_proposition_binding_trace(question, "yes", [item])
    candidate = _candidate_for_quote(trace, quote)

    assert candidate["authority_state"] == "retrieved_unverified"
    assert candidate["candidate_relevance"] is True
    assert candidate["actor"] == "current_paper"
    assert candidate["relation"] == candidate["predicate"] == "use"
    assert {"clinical", "corpu"} <= set(candidate["object"].split())
    assert candidate["qualifier"] == "none"
    assert candidate["quantifier"] == "none"
    assert candidate["scope"] == candidate["section_scope"] == "results"
    assert candidate["polarity"] == "yes"
    assert candidate["evidence_id"] == evidence_id
    assert candidate["quote"] == candidate["exact_span"] == quote
    assert candidate["span_start"] == local_start
    assert candidate["span_end"] == local_end
    assert candidate["canonical_start"] == 700 + local_start
    assert candidate["canonical_end"] == 700 + local_end
    expected_ref = f"{evidence_id}#quote:{700 + local_start}:{700 + local_end}"
    assert candidate["evidence_ref"] == candidate["exact_span_id"] == expected_ref


def test_irrelevant_candidate_trace_remains_missing() -> None:
    question = "Did the authors use the clinical corpus?"
    quote = "The architecture contains three encoder layers."
    item = _evidence("irrelevant", quote)

    trace = boolean_proposition_binding_trace(question, "yes", [item])
    candidate = _candidate_for_quote(trace, quote)

    assert candidate["authority_state"] == "missing"
    assert candidate["candidate_relevance"] is False
    assert candidate["evidence_id"] == identity_of(item).key
    assert candidate["quote"] == quote
    assert candidate["span_start"] == 0
    assert candidate["span_end"] == len(quote)


def test_repeated_quote_does_not_claim_a_false_exact_span_identity() -> None:
    question = "Did the authors use the clinical corpus?"
    quote = "We used the clinical corpus."
    item = _evidence("ambiguous", f"{quote} {quote}", canonical_start=900)

    trace = boolean_proposition_binding_trace(question, "yes", [item])
    candidates = [
        candidate
        for candidate in trace["proposition_candidates"]
        if candidate["quote"] == quote
    ]

    assert candidates
    assert all(candidate["evidence_ref"] == "" for candidate in candidates)
    assert all(candidate["exact_span_id"] == "" for candidate in candidates)
    assert all(candidate["span_start"] is None for candidate in candidates)
    assert all(candidate["span_end"] is None for candidate in candidates)
    assert all(candidate["canonical_start"] is None for candidate in candidates)
    assert all(candidate["canonical_end"] is None for candidate in candidates)


def test_trace_is_observational_and_does_not_change_terminal_answer() -> None:
    question = "Did the authors use the clinical corpus?"
    item = _evidence("support", "We used the clinical corpus.")
    original_item = deepcopy(item)

    before = _run_boolean(question, "yes", [item])
    trace = boolean_proposition_binding_trace(question, "yes", [item])
    after = _run_boolean(question, "yes", [item])

    assert trace["proposition_candidates"]
    assert item == original_item
    assert before.answer == after.answer == "yes"
    assert before.verify_decision.as_dict() == after.verify_decision.as_dict()
    assert before.guardrail_decision.as_dict() == after.guardrail_decision.as_dict()
    assert before.engine_terminal_commit == after.engine_terminal_commit


def test_runtime_projects_missing_verified_support_and_verified_conflict() -> None:
    question = "Did the authors use the clinical corpus?"
    missing = _run_boolean(
        question,
        "yes",
        [_evidence("unrelated", "The architecture contains three layers.")],
    )
    supported = _run_boolean(
        question,
        "yes",
        [_evidence("positive", "We used the clinical corpus.")],
    )
    conflict = _run_boolean(
        question,
        "yes",
        [
            _evidence("positive", "We used the clinical corpus.", page_label="1"),
            _evidence(
                "negative",
                "We did not use the clinical corpus.",
                page_label="2",
            ),
        ],
    )

    assert missing.verify_decision.typed_authority["state"] == "missing"
    assert supported.verify_decision.typed_authority["state"] == "verified_support"
    assert conflict.verify_decision.typed_authority["state"] == "verified_conflict"
    assert missing.answer == ABSTAIN_MESSAGE
    assert supported.answer == "yes"
    assert conflict.answer == "unanswerable"
