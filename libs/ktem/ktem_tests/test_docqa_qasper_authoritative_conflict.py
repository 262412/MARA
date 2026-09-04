from __future__ import annotations

from typing import Any

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.boolean_claim_verification import boolean_claim_authority
from ktem.docqa.boolean_proposition_evidence import classify_boolean_evidence_candidates
from ktem.docqa.controller import RetrieveDecision
from ktem.docqa.evidence import EvidenceBundle
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.execution import execute_controller_turn
from ktem.docqa.query_planning import bind_evidence_slots, build_query_plan
from ktem.docqa.verification import verify_decision

QUESTION = "Across pages 1 and 2, did the authors release the code?"
NEGATIVE_SPAN = "The authors did not release the code."
FOLLOWUP_SPAN = "The release statement describes packaging."
POSITIVE_SPAN = "The authors released the code publicly with the paper."
NEGATIVE_PAGE_SPAN = "The authors did not release the code for the final system."
NEGATIVE_SMOKE_SPAN = (
    "The authors did not release the code for the final evaluated system."
)


def _item(
    evidence_id: str,
    page_label: str,
    text: str,
    *,
    section_id: str = "results",
) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "document_id": "paper",
        "page_label": page_label,
        "section_id": section_id,
        "evidence_level": "page",
        "text": text,
    }


def _request(plan: Any | None = None) -> DocQARequest:
    return DocQARequest(
        prompt=QUESTION,
        retrieval_query=QUESTION,
        task_type="boolean",
        verification_mode="strict",
        verification_domain="qasper",
        route_policy="doc",
        allowed_routes=["doc_text", "hybrid"],
        selected_file_ids=["paper"],
        query_plan=plan,
        origin="benchmark",
    )


def _cross_page_items() -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        _item("positive", "1", POSITIVE_SPAN),
        _item("negative", "2", NEGATIVE_PAGE_SPAN),
    )


def _smoke_artifact_items() -> list[dict[str, Any]]:
    positive = _item(
        "positive-page",
        "1",
        (
            "Contract Smoke Study - Methods\n"
            f"{POSITIVE_SPAN}\n"
            "The release statement applies to the final evaluated system.\n"
            "Page 1"
        ),
    )
    negative = _item(
        "negative-page",
        "2",
        (
            "Contract Smoke Study - Correction\n"
            f"{NEGATIVE_SMOKE_SPAN}\n"
            "This correction explicitly supersedes the earlier release statement.\n"
            "Page 2"
        ),
    )
    positive_graph = {
        **_item("positive-graph-1", "1", f"Methods\n{POSITIVE_SPAN}"),
        "modality": "graph",
        "evidence_level": "graph",
        "element_id": "contract:paper:1",
    }
    stale_positive_graph = {
        **_item("positive-graph-2", "2", f"Methods\n{POSITIVE_SPAN}"),
        "modality": "graph",
        "evidence_level": "graph",
        "element_id": "contract:paper:2",
    }
    negative_graph = {
        **_item("negative-graph-2", "2", f"Correction\n{NEGATIVE_SMOKE_SPAN}"),
        "modality": "graph",
        "evidence_level": "graph",
        "element_id": "correction:paper:2",
    }
    return [positive, negative, positive_graph, stale_positive_graph, negative_graph]


def _bound_cross_page_plan(
    items: list[dict[str, Any]],
) -> Any:
    return bind_evidence_slots(
        build_query_plan(
            QUESTION,
            answer_type="boolean",
            verification_domain="qasper",
        ),
        items,
    )


def test_boolean_negation_is_derived_from_exact_proposition_span() -> None:
    item = _item(
        "negated-release",
        "1",
        f"{NEGATIVE_SPAN} {FOLLOWUP_SPAN}",
    )

    assessments = classify_boolean_evidence_candidates(QUESTION, "yes", item)
    by_span = {assessment.span_text: assessment for assessment in assessments}

    negative = by_span[NEGATIVE_SPAN]
    assert negative.proposition.polarity == "no"
    assert negative.classification == "contradicts"

    # A later lexical mention of a release statement is not evidence that the
    # proposition in the first span was positive.
    followup = by_span[FOLLOWUP_SPAN]
    assert followup.classification != "supports"

    authority = boolean_claim_authority(
        "Did the authors release the code?",
        "yes",
        [item],
    )
    assert authority is not None
    assert authority.status == "supported"
    assert authority.canonical_answer_polarity == "no"
    [selected] = authority.supporting
    assert selected.polarity == "no"
    assert selected.quote == NEGATIVE_SPAN
    assert FOLLOWUP_SPAN not in selected.quote


def test_page_locator_cannot_borrow_prior_relation_or_opposite_polarity() -> None:
    items = _smoke_artifact_items()
    negative = items[1]

    assessments = classify_boolean_evidence_candidates(QUESTION, "no", negative)
    assert all(
        assessment.span_text != "Page 2"
        or assessment.classification not in {"supports", "contradicts"}
        for assessment in assessments
    )

    authority = boolean_claim_authority(QUESTION, "no", items)
    assert authority is not None
    assert authority.status == "conflicting"
    assert {
        value.quote for value in (*authority.supporting, *authority.contradicting)
    } == {
        POSITIVE_SPAN,
        NEGATIVE_SMOKE_SPAN,
    }
    assert all("Page " not in value.quote for value in authority.supporting)
    assert all("Page " not in value.quote for value in authority.contradicting)

    plan = _bound_cross_page_plan(items)
    decision = verify_decision(
        _request(plan),
        RetrieveDecision(status="good", reason="ok"),
        EvidenceBundle(
            route="hybrid",
            items=items,
            metadata={"query_plan": plan.as_dict()},
        ),
        answer="no",
    )
    assert decision.status == "verified_conflict"
    assert decision.authoritative_conflict["required_evidence_coverage"] == 1.0


def test_smoke_artifact_bundle_commits_complete_conflict_terminal_state() -> None:
    items = _smoke_artifact_items()
    result = execute_controller_turn(
        _request(),
        retrieve=lambda *_args: {"evidence": items},
        generate=lambda *_args: "no",
    )

    decision = result.verify_decision.as_dict()
    conflict = decision["authoritative_conflict"]
    assert decision["status"] == "verified_conflict"
    assert decision["action"] == "abstain"
    assert decision["reason"] == "authoritative_conflict_abstention"
    assert conflict["required_evidence_coverage"] == 1.0
    assert {
        value["quote"]
        for side in ("positive_authorities", "negative_authorities")
        for value in conflict[side]
    } == {POSITIVE_SPAN, NEGATIVE_SMOKE_SPAN}

    assert result.answer == "unanswerable"
    terminal = result.engine_terminal_state
    assert terminal["normalized_candidate_label"] == "unanswerable"
    assert terminal["terminal_reason"] == "authoritative_conflict_abstention"
    assert terminal["authoritative_conflict"] == conflict
    plan = result.evidence_bundle.metadata["query_plan"]
    assert plan["stage"] == "verified"
    assert plan["state_authority"] == "boolean_authoritative_conflict.v1"
    assert {slot["status"] for slot in plan["evidence_slots"]} == {"verified_conflict"}
    assert not any(
        event.get("verifier_recovery_attempt") for event in result.controller_trace
    )
    [stop] = [event for event in result.controller_trace if event.get("stop_reason")]
    assert stop["stop_reason"] == "authority_conflict_resolved"


def test_two_sided_authorities_are_disjoint_by_canonical_span_identity() -> None:
    positive, negative = _cross_page_items()
    authority = boolean_claim_authority(QUESTION, "yes", [positive, negative])

    assert authority is not None
    assert authority.status == "conflicting"
    assert authority.canonical_answer_polarity == ""
    assert len(authority.supporting) == 1
    assert len(authority.contradicting) == 1

    support = authority.supporting[0]
    contradiction = authority.contradicting[0]
    assert support.polarity == "yes"
    assert contradiction.polarity == "no"
    assert support.evidence_id == identity_of(positive).key
    assert contradiction.evidence_id == identity_of(negative).key
    assert {(support.evidence_id, support.evidence_ref, support.span_id)}.isdisjoint(
        {(contradiction.evidence_id, contradiction.evidence_ref, contradiction.span_id)}
    )
    assert support.evidence_ref
    assert support.span_id
    assert contradiction.evidence_ref
    assert contradiction.span_id


def test_opposite_polarities_from_one_span_fail_closed_as_internal_inconsistency() -> (
    None
):
    item = _item(
        "same-span",
        "1",
        "The authors released the code, but did not release the code.",
    )

    authority = boolean_claim_authority(
        "Did the authors release the code?",
        "yes",
        [item],
    )

    assert authority is not None
    assert authority.status == "unknown"
    assert "internal" in authority.reason
    assert not getattr(authority, "authoritative_conflict", None)


def test_verify_decision_exposes_typed_authoritative_conflict_without_polarity() -> (
    None
):
    positive, negative = _cross_page_items()
    items = [positive, negative]
    plan = _bound_cross_page_plan(items)
    request = _request(plan)
    bundle = EvidenceBundle(
        route="doc_text",
        items=items,
        metadata={"query_plan": plan.as_dict()},
    )

    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="ok"),
        bundle,
        answer="yes",
    )
    payload = decision.as_dict()

    assert payload["status"] == "verified_conflict"
    assert payload["action"] == "abstain"
    assert payload["reason"] == "authoritative_conflict_abstention"
    assert payload["canonical_answer_polarity"] == ""
    assert payload["boolean_authority_status"] == "verified_conflict"
    conflict = payload["authoritative_conflict"]
    assert conflict["contract_id"] == "boolean_authoritative_conflict.v1"
    assert conflict["status"] == "verified_conflict"
    assert conflict["required_evidence_coverage"] == 1.0
    assert set(conflict["required_slot_ids"]) == {
        "support:proposition",
        "support:left_subject",
        "support:right_subject",
    }
    assert set(conflict["verified_required_slot_ids"]) == set(
        conflict["required_slot_ids"]
    )
    assert payload["verified_citations"] == []

    by_side = {
        "positive_authorities": (positive, POSITIVE_SPAN, "yes"),
        "negative_authorities": (negative, NEGATIVE_PAGE_SPAN, "no"),
    }
    authority_keys: dict[str, set[tuple[str, str, str]]] = {}
    for side, (item, quote, polarity) in by_side.items():
        entries = conflict[side]
        assert entries
        entry = next(
            value for value in entries if value["evidence_id"] == identity_of(item).key
        )
        assert entry["evidence_ref"]
        assert entry["span_id"]
        assert entry["quote"] == quote
        assert entry["polarity"] == polarity
        assert entry["source_id"] == "paper"
        assert entry["page_label"] == item["page_label"]
        assert item["text"][entry["span_start"] : entry["span_end"]] == quote
        authority_keys[side] = {
            (entry["evidence_id"], entry["evidence_ref"], entry["span_id"])
        }
    assert authority_keys["positive_authorities"].isdisjoint(
        authority_keys["negative_authorities"]
    )


def test_execute_controller_turn_commits_conflict_terminal_state_fail_closed() -> None:
    positive, negative = _cross_page_items()
    items = [positive, negative]
    result = execute_controller_turn(
        _request(),
        retrieve=lambda *_args: {"evidence": items},
        generate=lambda *_args: "yes",
    )

    assert result.answer == "unanswerable"
    assert result.engine_terminal_state["terminal_reason"] == (
        "authoritative_conflict_abstention"
    )
    decision = result.verify_decision.as_dict()
    conflict = decision["authoritative_conflict"]
    assert result.engine_terminal_state["verify_decision"] == decision
    assert result.engine_terminal_state["authoritative_conflict"] == conflict
    assert result.engine_terminal_state["normalized_candidate_label"] == (
        "unanswerable"
    )
    assert decision["status"] == "verified_conflict"
    assert decision["action"] == "abstain"
    assert decision["canonical_answer_polarity"] == ""
    assert decision["verified_citations"] == []

    metadata = result.evidence_bundle.metadata
    assert metadata["boolean_authoritative_conflict"] == conflict
    slot_states = metadata["verification_slot_states"]
    assert {state["status"] for state in slot_states} == {"verified_conflict"}
    assert {state["slot_id"] for state in slot_states} == {
        "support:proposition",
        "support:left_subject",
        "support:right_subject",
    }
    query_plan = metadata["query_plan"]
    assert {slot["status"] for slot in query_plan["evidence_slots"]} == {
        "verified_conflict"
    }
    required_ids = {
        evidence_id
        for slot in query_plan["evidence_slots"]
        for evidence_id in slot["evidence_ids"]
    }
    assert required_ids == {identity_of(positive).key, identity_of(negative).key}
    assert metadata.get("verified_evidence", []) == []
    assert metadata.get("verified_claim_support_evidence", []) == []
    assert metadata.get("verified_claim_support_spans", []) == []
