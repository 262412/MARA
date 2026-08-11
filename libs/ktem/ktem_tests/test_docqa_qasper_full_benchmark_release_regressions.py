from __future__ import annotations

import json
from types import SimpleNamespace
from typing import Any

import pytest
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.controller import RetrieveDecision, evaluate_retrieval_quality
from ktem.docqa.evidence import EvidenceBundle
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_planning import select_planned_evidence
from ktem.docqa.query_evidence_binding import bind_evidence_slots
from ktem.docqa.query_plan_schema import EvidenceSlot, QueryPlan
from ktem.docqa.query_planning import build_query_plan
from ktem.docqa.verification import (
    VerifyDecision,
    verify_decision,
    with_verification_evidence,
)
from ktem.docqa.verification_slot_support import enforce_verification_slot_support
from ktem.reasoning.mara_route_scorer import score_adaptive_route

from benchmark.answer_finalizer import finalize_prediction_answer
from benchmark.qasper_answerability import verify_qasper_answerability
from benchmark.task_answer_contracts import (
    apply_task_answer_contract,
    synchronize_terminal_answer_state,
)


class _Verifier:
    def __init__(self, verdict: str, quote: str, evidence_ref: str = "") -> None:
        self.response = json.dumps(
            {
                "verdict": verdict,
                "evidence_ref": evidence_ref,
                "evidence_quote": quote,
            }
        )

    def __call__(self, _prompt: str, **_kwargs: Any) -> Any:
        return SimpleNamespace(text=self.response)


def _item(
    evidence_id: str,
    text: str,
    *,
    canonical_start: int | None = None,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "section_id": "results",
        "text": text,
    }
    if canonical_start is not None:
        item["canonical_start"] = canonical_start
        item["canonical_end"] = canonical_start + len(text)
    return item


def test_verification_only_missing_slot_does_not_block_generation() -> None:
    question = "Did the authors evaluate the model on clinical tasks?"
    plan = QueryPlan(
        answer_type="boolean",
        question_type="simple_fact",
        plan_id="plan:qasper-verification-only",
        evidence_slots=(
            EvidenceSlot(
                slot_id="support:boolean_proposition",
                role="support",
                statement_kind="boolean_proposition",
                required_for_retrieval=False,
                required_for_verification=True,
                status="missing",
            ),
        ),
    )
    evidence = _item(
        "retrieved-context",
        "The paper describes the evaluation protocol and its clinical tasks.",
    )
    metadata = {
        "evidence": [evidence],
        "selected_evidence": [evidence],
        "generation_context_evidence": [evidence],
        "bound_query_plan": plan.as_dict(),
        "missing_required_slot_count": 1,
    }

    decision = evaluate_retrieval_quality(
        "doc_text",
        metadata,
        prompt=question,
        verification_domain="qasper",
    )

    assert decision.status == "good"
    assert decision.retry is False


def test_verification_only_slot_reaches_claim_verification_before_abstention() -> None:
    question = "Did the authors evaluate the model on clinical tasks?"
    request = DocQARequest(
        prompt=question,
        task_type="boolean",
        verification_mode="strict",
        verification_domain="qasper",
        query_plan=build_query_plan(
            question,
            answer_type="boolean",
            verification_domain="qasper",
        ),
    )
    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        EvidenceBundle(
            route="doc_text",
            items=[
                _item(
                    "candidate",
                    "The paper describes an evaluation protocol for clinical tasks.",
                )
            ],
        ),
        "Yes, the authors evaluated the model on clinical tasks.",
    )

    assert decision.status != "not_enough_evidence"
    assert decision.claims


def test_supported_claim_atomically_promotes_only_canonical_slot_evidence() -> None:
    question = "What drove the reduction in SG&A expenses in fiscal year 2023?"
    selected = _item(
        "page-2",
        "Lower employee-related expenses drove the reduction in SG&A expenses.",
    )
    distractor = _item("page-6", "SG&A expenses are listed in this table.")
    selected_id = identity_of(selected).key
    distractor_id = identity_of(distractor).key
    plan = QueryPlan(
        answer_type="free_text",
        question_type="long_form",
        plan_id="plan:finance-support",
        evidence_slots=(
            EvidenceSlot(
                slot_id="support:primary",
                role="support",
                metric="drove reduction sg expenses fiscal year",
                required_for_retrieval=True,
                required_for_verification=True,
                status="filled",
                evidence_ids=(distractor_id,),
            ),
        ),
    )
    request = DocQARequest(
        prompt=question,
        verification_mode="strict",
        verification_domain="finance",
        query_plan=plan,
        query_plan_state_version=1,
    )
    decision = VerifyDecision(
        mode="strict",
        status="supported",
        reason="supported",
        action="return",
        claims=["Lower employee-related expenses drove the reduction in SG&A."],
        verified_citations=[selected_id],
        claim_results=[
            {
                "claim_id": "claim:1",
                "claim": "Lower employee-related expenses drove the reduction in SG&A.",
                "status": "supported",
                "supporting_evidence_ids": [selected_id],
                "contradicting_evidence_ids": [],
            }
        ],
    )

    bundle = with_verification_evidence(
        EvidenceBundle(route="doc_text", items=[distractor, selected]),
        decision,
        request,
    )

    [slot] = request.query_plan.evidence_slots
    assert slot.status == "verified_support"
    assert slot.evidence_ids == (selected_id,)
    assert bundle.metadata["query_plan"]["state_authority"] == (
        "verified_claim_support.v1"
    )
    assert bundle.metadata["query_plan"]["state_version"] == 2
    [state] = bundle.metadata["verification_slot_states"]
    assert state == {
        "slot_id": "support:primary",
        "status": "verified_support",
        "evidence_ids": [selected_id],
    }


def test_binding_failure_still_abstains_without_selected_support() -> None:
    question = "Did the authors evaluate the model on clinical tasks?"
    selected = _item("selected", "The paper evaluates the model on clinical tasks.")
    foreign = _item("foreign", "The paper evaluates the model on clinical tasks.")
    plan = bind_evidence_slots(
        build_query_plan(
            question,
            answer_type="boolean",
            verification_domain="qasper",
        ),
        [selected],
    )
    request = DocQARequest(
        prompt=question,
        verification_mode="strict",
        verification_domain="qasper",
        query_plan=plan,
    )
    foreign_id = identity_of(foreign).key
    decision = VerifyDecision(
        mode="strict",
        status="supported",
        reason="supported",
        claims=[question],
        verified_citations=[foreign_id],
        claim_results=[
            {
                "claim_id": "claim:1",
                "claim": question,
                "status": "supported",
                "supporting_evidence_ids": [foreign_id],
                "contradicting_evidence_ids": [],
            }
        ],
    )

    enforced = enforce_verification_slot_support(
        request,
        decision,
        EvidenceBundle(route="doc_text", items=[selected]),
        prompt=question,
        domain="qasper",
    )

    assert enforced.status == "unknown"
    assert enforced.action == "abstain"
    assert "support:boolean_proposition" in enforced.reason


def test_successful_post_verifier_keeps_canonical_ids_across_all_support_stages() -> None:
    question = "Did the authors evaluate the model on clinical tasks?"
    quote = "We evaluated the model on clinical tasks."
    evidence = _item("evaluation", quote, canonical_start=100)
    canonical_id = identity_of(evidence).key
    plan = build_query_plan(
        question,
        answer_type="boolean",
        verification_domain="qasper",
    )
    prediction: dict[str, Any] = {
        "question": question,
        "answer_type": "boolean",
        "predicted_answer": "unanswerable",
        "route": "text_rag",
        "gold_evidence": ["anonymous-support"],
        "evidence_bundle": {"items": [evidence], "metadata": {}},
        "evidence_metadata": {
            "selected_evidence": [evidence],
            "generation_context_evidence": [evidence],
            "query_plan": plan.as_dict(),
        },
        "structured_citations": [],
        "predicted_citations": [],
    }

    finalize_prediction_answer(
        prediction,
        dataset_name="qasper_typed",
        mode="scoring_adapter_v1",
    )
    assert apply_task_answer_contract(
        prediction,
        dataset_name="qasper_typed",
        llm_factory=lambda: _Verifier("yes_complete", quote),
    )
    finalize_prediction_answer(
        prediction,
        dataset_name="qasper_typed",
        mode="scoring_adapter_v1",
    )
    assert synchronize_terminal_answer_state(prediction)

    [slot] = prediction["evidence_metadata"]["query_plan"]["evidence_slots"]
    assert slot["status"] == "verified_support"
    assert slot["evidence_ids"] == [canonical_id]
    trace = prediction["evidence_metadata"]["qasper_answerability"]
    assert trace["authoritative_quote_evidence_id"] == canonical_id
    assert trace["final_support_evidence_ids"] == [canonical_id]
    assert trace["verifier_input_evidence_ids"] == canonical_id
    assert trace["verifier_required_authority_status"] == "complete"
    assert trace["verifier_required_evidence_coverage"] == "1.000000"
    assert [
        identity_of(item).key
        for item in prediction["evidence_metadata"]["verified_claim_support_evidence"]
    ] == [canonical_id]
    assert prediction["verify_decision"]["verified_citations"] == [canonical_id]
    assert [item["evidence_id"] for item in prediction["structured_citations"]] == [
        canonical_id
    ]
    assert [
        item["evidence_id"]
        for item in prediction["terminal_answer_state"]["emitted_citations"]
    ] == [canonical_id]


@pytest.mark.parametrize(
    ("evidence_ref", "items", "quote"),
    (
        (
            "",
            [_item("support", "The paper reports clinical results.")],
            "Not in source.",
        ),
        (
            "",
            [
                _item(
                    "first", "The paper reports clinical results.", canonical_start=0
                ),
                _item(
                    "second", "The paper reports clinical results.", canonical_start=100
                ),
            ],
            "The paper reports clinical results.",
        ),
        (
            "E9:S9",
            [
                _item(
                    "first", "The paper reports clinical results.", canonical_start=0
                ),
                _item(
                    "second", "The paper reports clinical results.", canonical_start=100
                ),
            ],
            "The paper reports clinical results.",
        ),
    ),
)
def test_no_ambiguous_and_wrong_ref_quotes_fail_closed(
    evidence_ref: str,
    items: list[dict[str, Any]],
    quote: str,
) -> None:
    result = verify_qasper_answerability(
        _Verifier("yes_complete", quote, evidence_ref),
        question="Did the authors report clinical results?",
        answer_type="boolean",
        evidence="\n\n".join(item["text"] for item in items),
        evidence_items=items,
        candidate_answer="unanswerable",
    )

    assert result.answer == "unanswerable"
    assert result.trace["reason"] in {
        "ungrounded_quote",
        "quote_identity_unresolved",
        "evidence_ref_quote_mismatch",
    }
    assert result.trace.get("authoritative_quote_evidence_id") is None


def test_unique_wrong_ref_rebind_regression_is_preserved() -> None:
    quote = "We evaluated the model on clinical tasks."
    result = verify_qasper_answerability(
        _Verifier("yes_complete", quote, "E2:S1"),
        question="Did the authors evaluate the model on clinical tasks?",
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("support", quote)],
        candidate_answer="unanswerable",
    )

    assert result.answer == "yes"
    assert result.trace["evidence_ref_rebound"] == "true"
    assert result.trace["authoritative_quote_evidence_id"] == "evidence:paper:support"


_ROUTE_PROBE = {
    "text": {
        "evidence_count": 2,
        "top_score": 0.92,
        "top_margin": 0.2,
        "locator_quality": 1.0,
        "has_text_or_ocr": True,
    },
    "graph": {
        "evidence_count": 2,
        "top_score": 0.92,
        "top_margin": 0.2,
        "locator_quality": 1.0,
        "has_text_or_ocr": True,
    },
}


def test_1dc2_style_request_without_graph_intent_keeps_doc_text() -> None:
    decision = score_adaptive_route(
        {"task_type": "qa", "modalities": ["text"], "scope": "multi_document"},
        question="Do the authors conduct experiments on the tasks mentioned?",
        allowed_routes=["doc_text", "graph_global"],
        route_probe=_ROUTE_PROBE,
    )

    assert decision["routing_features"]["graph_intent"] is False
    assert decision["route"] == "doc_text"


def test_explicit_graph_request_is_not_normalized_to_doc_text() -> None:
    decision = score_adaptive_route(
        {"task_type": "qa", "modalities": ["text"], "scope": "multi_document"},
        question="Do the authors conduct experiments on the tasks mentioned?",
        allowed_routes=["doc_text", "graph_global"],
        route_probe=_ROUTE_PROBE,
        planner_route="graph_global",
        planner_reason="Explicit graph route requested.",
    )

    assert decision["route"] == "graph_global"


def test_cross_page_boolean_keeps_invalid_second_page_out_of_proposition_slot() -> None:
    question = "Across pages 1 and 2, did the authors release the code?"
    first = _item(
        "page-1",
        "The authors released the code publicly with the paper. Page 1",
    )
    first.update({"page_label": "1", "modality": "image", "evidence_level": "page"})
    second = _item(
        "page-2",
        "The authors evaluated the code on Page 2.",
    )
    second.update({"page_label": "2", "modality": "image", "evidence_level": "page"})
    plan = bind_evidence_slots(
        build_query_plan(
            question,
            answer_type="boolean",
            verification_domain="qasper",
        ),
        [first, second],
    )

    proposition, _left, _right = plan.evidence_slots
    assert proposition.status == "missing"
    assert proposition.evidence_ids == ()


def test_e971_artifact_candidate_stays_generation_context_without_retry() -> None:
    question = "Are the automatically constructed datasets subject to quality control?"
    request = DocQARequest(
        prompt=question,
        controller_question=question,
        retrieval_query=question,
        task_type="boolean",
        verification_domain="qasper",
    )
    selected, metadata = select_planned_evidence(
        request,
        [
            _item(
                "artifact-control",
                "We find automatically constructing probes to be vulnerable to annotation artifacts, which we carefully control for.",
            )
        ],
    )

    assert selected
    assert selected[0]["evidence_id"] == "artifact-control"
    [stage] = metadata["evidence_selection_trace"]["evidence_stage_trace"]
    assert stage["selected_in_context"] is True
    assert metadata["missing_required_slot_count"] == 0
    assert metadata["second_round_requests"] == []


def test_wrong_polarity_is_corrected_without_abstaining_valid_answer() -> None:
    quote = "We evaluated the model on clinical tasks."
    result = verify_qasper_answerability(
        _Verifier("yes_complete", quote),
        question="Did the authors evaluate the model on clinical tasks?",
        answer_type="boolean",
        evidence=quote,
        evidence_items=[_item("support", quote)],
        candidate_answer="no",
    )

    assert result.answer == "yes"
    assert result.trace["action"] == "corrected_polarity"
