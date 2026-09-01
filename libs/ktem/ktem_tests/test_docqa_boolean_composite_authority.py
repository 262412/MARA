from __future__ import annotations

from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.boolean_claim_verification import boolean_claim_authority
from ktem.docqa.boolean_conjunction import boolean_conjunction_spec
from ktem.docqa.controller import RetrieveDecision
from ktem.docqa.evidence import EvidenceBundle
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.execution import execute_controller_turn
from ktem.docqa.query_planning import build_query_plan
from ktem.docqa.verification import verify_decision, with_verification_evidence

QUESTION = "Did the authors evaluate both clinical and legal datasets?"


def _item(
    evidence_id: str,
    text: str,
    *,
    source_id: str = "paper",
) -> dict[str, str]:
    return {
        "evidence_id": evidence_id,
        "source_id": source_id,
        "section_id": "experiments",
        "text": text,
    }


def _premises() -> list[dict[str, str]]:
    return [
        _item("clinical", "We evaluate the model on a clinical dataset."),
        _item("legal", "We evaluate the model on a legal dataset."),
    ]


def _qasper_request(question: str = QUESTION) -> DocQARequest:
    plan = build_query_plan(
        question,
        answer_type="boolean",
        verification_domain="qasper",
    )
    return DocQARequest(
        prompt=question,
        task_type="boolean",
        verification_mode="strict",
        verification_domain="qasper",
        query_plan=plan,
        query_plan_state_version=1,
    )


def test_two_exact_spans_form_one_explicit_conjunctive_authority() -> None:
    items = _premises()

    authority = boolean_claim_authority(QUESTION, "yes", items)

    assert authority is not None
    assert authority.status == "supported"
    assert authority.reason == "composite_boolean_proposition"
    assert {value.evidence_id for value in authority.supporting} == {
        identity_of(item).key for item in items
    }
    assert authority.selected_derivation_id
    [derivation] = authority.authority_derivations
    assert derivation.derivation_id == authority.selected_derivation_id
    assert derivation.rule_id == "same_source_argument_conjunction.v1"
    assert derivation.premise_mode == "all_required"
    assert derivation.semantics == "open_world"
    assert derivation.status == "verified"
    assert set(derivation.required_argument_tokens) == set(
        derivation.covered_argument_tokens
    )
    assert len(derivation.premise_refs) == 2


def test_non_overlapping_spans_in_one_evidence_item_are_distinct_premises() -> None:
    item = _item(
        "combined",
        (
            "We evaluate the model on a clinical dataset. "
            "We evaluate the model on a legal dataset."
        ),
    )

    authority = boolean_claim_authority(QUESTION, "yes", [item])

    assert authority is not None
    assert authority.status == "supported"
    [derivation] = authority.authority_derivations
    assert len(derivation.premise_refs) == 2
    assert len(set(derivation.premise_refs)) == 2
    assert set(derivation.premise_evidence_ids) == {identity_of(item).key}


def test_composite_authority_commits_every_premise_to_slots_and_citations() -> None:
    items = _premises()
    bundle = EvidenceBundle(route="doc_text", items=items)
    request = _qasper_request()

    decision = verify_decision(
        request,
        RetrieveDecision(status="good", reason="retrieved"),
        bundle,
        "yes",
    )
    projected = with_verification_evidence(bundle, decision, request)
    evidence_ids = [identity_of(item).key for item in items]

    assert decision.status == "supported"
    assert decision.boolean_authority_status == "verified_support"
    assert decision.authoritative_evidence_id == ""
    assert set(decision.verified_citations) == set(evidence_ids)
    assert decision.selected_derivation_id
    [claim] = decision.claim_results
    assert claim["authority_status"] == "composite_exact"
    assert claim["selected_derivation_id"] == decision.selected_derivation_id
    [derivation] = decision.typed_authority["authority_derivations"]
    assert derivation["derivation_id"] == decision.selected_derivation_id
    [slot] = request.query_plan.evidence_slots
    assert slot.status == "verified_support"
    assert set(slot.evidence_ids) == set(evidence_ids)
    assert set(
        projected.metadata["verified_claim_support_by_claim"][claim["claim_id"]]
    ) == set(evidence_ids)


def test_missing_conjunct_remains_unknown() -> None:
    authority = boolean_claim_authority(QUESTION, "yes", _premises()[:1])

    assert authority is not None
    assert authority.status == "unknown"
    assert authority.supporting == ()
    assert authority.authority_derivations == ()


def test_cross_source_fragments_cannot_form_a_conjunctive_authority() -> None:
    items = _premises()
    items[1] = _item(
        "legal",
        "We evaluate the model on a legal dataset.",
        source_id="other-paper",
    )

    authority = boolean_claim_authority(QUESTION, "yes", items)

    assert authority is not None
    assert authority.status == "unknown"
    assert authority.authority_derivations == ()


def test_existential_event_binding_is_not_inferred_across_spans() -> None:
    question = "Did any experiment evaluate a clinical and a legal dataset?"

    authority = boolean_claim_authority(question, "yes", _premises())

    assert authority is not None
    assert authority.status == "unknown"
    assert authority.authority_derivations == ()


def test_comparison_relation_is_not_reduced_to_independent_conjuncts() -> None:
    question = "Did the authors compare clinical versus legal datasets?"

    authority = boolean_claim_authority(question, "yes", _premises())

    assert authority is not None
    assert authority.status == "unknown"
    assert authority.authority_derivations == ()


def test_same_event_requirement_is_not_inferred_across_spans() -> None:
    question = "Did the same experiment evaluate clinical and legal datasets?"

    authority = boolean_claim_authority(question, "yes", _premises())

    assert authority is not None
    assert authority.authority_derivations == ()


def test_coordinated_predicates_are_not_treated_as_argument_conjunction() -> None:
    question = "Did the authors train and evaluate clinical datasets?"

    authority = boolean_claim_authority(question, "yes", _premises())

    assert authority is not None
    assert authority.authority_derivations == ()


def test_coordinated_gerunds_are_not_treated_as_argument_conjunction() -> None:
    question = (
        "Did the authors experiment with offering candidate corrections and voting "
        "on model outputs?"
    )

    authority = boolean_claim_authority(question, "yes", _premises())

    assert boolean_conjunction_spec(question) is None
    assert authority is not None
    assert authority.authority_derivations == ()


def test_entity_type_join_records_declaration_and_empirical_premises() -> None:
    declaration = _item(
        "definition",
        "We present AtlasCV and AtlasNLP, two open-source toolkits for research.",
    )
    experiment = _item(
        "experiment",
        "In our experiments, we evaluate AtlasCV on two benchmark datasets.",
    )

    authority = boolean_claim_authority(
        "Did the authors experiment with the toolkits?",
        "yes",
        [declaration, experiment],
    )

    assert authority is not None
    assert authority.status == "supported"
    assert {value.evidence_id for value in authority.supporting} == {
        identity_of(declaration).key,
        identity_of(experiment).key,
    }
    [derivation] = authority.authority_derivations
    assert derivation.rule_id == "same_source_entity_type_join.v1"
    assert dict(derivation.bindings)["entity_type"] == "toolkit"
    assert len(derivation.premise_refs) == 2


def test_derivation_identity_is_stable_under_evidence_permutation() -> None:
    forward = boolean_claim_authority(QUESTION, "yes", _premises())
    reverse = boolean_claim_authority(QUESTION, "yes", list(reversed(_premises())))

    assert forward is not None and reverse is not None
    assert forward.selected_derivation_id == reverse.selected_derivation_id
    assert forward.authority_derivations == reverse.authority_derivations


def test_disjunction_is_not_promoted_to_a_conjunctive_authority() -> None:
    question = "Did the authors evaluate a clinical or legal dataset?"

    authority = boolean_claim_authority(question, "yes", _premises())

    assert authority is not None
    assert authority.authority_derivations == ()


def test_composite_authority_is_available_outside_qasper() -> None:
    execution = execute_controller_turn(
        DocQARequest(
            prompt=QUESTION,
            retrieval_query=QUESTION,
            task_type="boolean",
            verification_mode="strict",
            verification_domain="general",
            route_policy="doc",
            allowed_routes=["doc_text"],
            selected_file_ids=["paper"],
        ),
        retrieve=lambda *_args: {"evidence": _premises()},
        generate=lambda *_args: "yes",
    )

    assert execution.answer == "yes"
    assert execution.verify_decision.status == "supported"
    assert len(execution.verify_decision.verified_citations) == 2
    assert execution.verify_decision.typed_authority["contract_id"] == (
        "typed_proposition_authority.v1"
    )
    assert execution.verify_decision.typed_authority["state"] == "verified_support"
    assert len(execution.verify_decision.typed_authority["authority_atoms"]) == 2
    assert len(execution.verify_decision.typed_authority["authority_derivations"]) == 1
    [claim] = execution.verify_decision.claim_results
    assert claim["authority_status"] == "composite_exact"
    assert claim["selected_derivation_id"]
