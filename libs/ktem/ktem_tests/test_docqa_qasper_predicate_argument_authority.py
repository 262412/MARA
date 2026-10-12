from __future__ import annotations

from typing import Any

import pytest
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.execution import ABSTAIN_MESSAGE, execute_controller_turn

QUESTION = (
    "What argumentation phenomena encountered in actual data are now "
    "accounted for by this work?"
)
CONTRIBUTION_LIST = (
    "We deal with actual Web data and take up the challenges given by the "
    "variety of registers, multiple domains, and unrestricted noisy "
    "user-generated Web discourse. We bridge the gap between normative "
    "argumentation theories and argumentation phenomena encountered in actual "
    "data by adapting an argumentation model tested in an extensive annotation "
    "study. We create a new gold standard corpus and experiment with several "
    "machine learning methods to identify argument components."
)
UNSUPPORTED_ANSWER = (
    "The argumentation phenomena encountered in actual data that are now "
    "accounted for by this work include the challenges posed by the variety of "
    "registers, multiple domains, and unrestricted noisy user-generated Web "
    "discourse. The work bridges the gap between normative argumentation "
    "theories and argumentation phenomena encountered in actual data by "
    "adapting an argumentation model tested in an extensive annotation study. "
    "It also addresses the need for a new gold standard corpus and experiments "
    "with several machine learning methods to identify argument components."
)
DIRECT_AUTHORITY = (
    "Implicit premises encountered in actual data are now accounted for by this work."
)


def _request(
    route_policy: str,
    allowed_routes: list[str],
    agent_mode: str | None,
) -> DocQARequest:
    return DocQARequest(
        prompt=QUESTION,
        controller_question=QUESTION,
        retrieval_query=QUESTION,
        task_type="free_text",
        verification_mode="strict",
        verification_domain="qasper",
        route_policy=route_policy,
        allowed_routes=allowed_routes,
        agent_mode=agent_mode,
        selected_file_ids=["paper"],
        origin="benchmark",
    )


def _evidence(text: str) -> dict[str, Any]:
    return {
        "evidence_id": "authority",
        "source_id": "paper",
        "section_id": "abstract",
        "text": text,
    }


@pytest.mark.parametrize(
    ("route_policy", "allowed_routes", "agent_mode"),
    (
        ("doc", ["doc_text"], None),
        ("auto", ["doc_text", "hybrid"], None),
        ("auto", ["doc_text", "hybrid"], "thorough"),
    ),
    ids=("text_rag", "controller_auto", "crag_guarded"),
)
def test_contribution_list_cannot_fill_account_for_relation_across_routes(
    route_policy: str,
    allowed_routes: list[str],
    agent_mode: str | None,
) -> None:
    result = execute_controller_turn(
        _request(route_policy, allowed_routes, agent_mode),
        retrieve=lambda *_args: {"evidence": [_evidence(CONTRIBUTION_LIST)]},
        generate=lambda *_args: UNSUPPORTED_ANSWER,
    )

    assert result.answer == ABSTAIN_MESSAGE
    assert result.engine_terminal_answer == "unanswerable"
    assert result.verify_decision.status == "unknown"
    assert result.verify_decision.verified_citations == []
    assert result.verify_decision.authoritative_evidence_id == ""
    assert result.verify_decision.typed_authority["state"] == "missing"
    assert result.verify_decision.typed_authority["authority_atoms"] == []
    [slot] = result.evidence_bundle.metadata["query_plan"]["evidence_slots"]
    assert slot["slot_id"] == "support:answer_relation"
    assert slot["status"] != "verified_support"


def test_exact_account_for_predicate_argument_relation_is_authoritative() -> None:
    result = execute_controller_turn(
        _request("doc", ["doc_text"], None),
        retrieve=lambda *_args: {"evidence": [_evidence(DIRECT_AUTHORITY)]},
        generate=lambda *_args: "Implicit premises.",
    )

    assert result.answer == "Implicit premises."
    assert result.engine_terminal_answer == "Implicit premises."
    assert result.verify_decision.status == "supported"
    assert result.verify_decision.typed_authority["state"] == "verified_support"
    [atom] = result.verify_decision.typed_authority["authority_atoms"]
    assert atom["predicate"] == "account_for"
    assert atom["actor"] == "current_paper"
    assert atom["object"] == "Implicit premises"
    assert atom["object_role"] == "patient"
    assert atom["object_type"] == "argumentation phenomena"
    assert atom["question_scope"] == "actual data"
    assert atom["quote"] == DIRECT_AUTHORITY


def test_account_for_words_without_required_roles_do_not_fill_relation() -> None:
    evidence = _evidence(
        "This work gives an account of several experiments. Actual data are "
        "used to evaluate the new corpus."
    )
    result = execute_controller_turn(
        _request("doc", ["doc_text"], None),
        retrieve=lambda *_args: {"evidence": [evidence]},
        generate=lambda *_args: "Several experiments.",
    )

    assert result.engine_terminal_answer == "unanswerable"
    assert result.verify_decision.status == "unknown"
    assert result.verify_decision.typed_authority["authority_atoms"] == []


def test_same_sentence_non_argument_cannot_fill_account_for_relation() -> None:
    evidence = _evidence(
        "This work accounts for implicit premises in actual data, while machine "
        "learning methods identify argument components."
    )
    result = execute_controller_turn(
        _request("doc", ["doc_text"], None),
        retrieve=lambda *_args: {"evidence": [evidence]},
        generate=lambda *_args: "Machine learning methods.",
    )

    assert result.engine_terminal_answer == "unanswerable"
    assert result.verify_decision.status == "unknown"
    assert result.verify_decision.typed_authority["authority_atoms"] == []


def test_answer_object_drops_unconfirmed_extension_beyond_the_predicate_argument() -> (
    None
):
    question = "What background knowledge do they leverage?"
    request = DocQARequest(
        prompt=question,
        retrieval_query=question,
        task_type="free_text",
        verification_mode="strict",
        verification_domain="qasper",
        route_policy="doc",
        allowed_routes=["doc_text"],
        selected_file_ids=["paper"],
        origin="benchmark",
    )
    evidence = _evidence(
        "Our method leverages labeled features as prior knowledge. Class "
        "distribution is discussed separately as an analysis target."
    )

    result = execute_controller_turn(
        request,
        retrieve=lambda *_args: {"evidence": [evidence]},
        generate=lambda *_args: "labeled features and class distribution",
    )

    assert result.engine_terminal_answer == "labeled features"
    assert result.verify_decision.status == "supported"
    assert result.verify_decision.typed_authority["state"] == "verified_support"
    assert result.verify_decision.typed_authority["authority_atoms"]
