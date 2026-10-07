import pytest
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.typed_retrieval_recovery import recovery_query, recovery_query_metadata

TITLE = "A study of morphology in context"


def _request(question, **overrides):
    return DocQARequest(
        prompt=question,
        verification_domain="qasper",
        selected_source_title=TITLE,
        **{"selected_file_ids": ["paper"], "active_file_id": "paper", **overrides},
    )


@pytest.mark.parametrize(
    "question",
    [
        "What type of inflections are considered?",
        "Which kind of inputs are considered?",
        "What sort of outputs are considered?",
    ],
)
def test_generic_type_question_keeps_selected_document_recovery_context(question):
    request = _request(question)

    assert recovery_query(request, question) == f"{question} {TITLE}"
    assert recovery_query_metadata(request)["document_context"] == {
        "kind": "selected_document_title",
        "text": TITLE,
    }


@pytest.mark.parametrize(
    "question",
    [
        "What does inflection mean?",
        "What NDCG score did the final submission achieve?",
        "What kind of data does the proposed model use?",
    ],
)
def test_explicit_relation_or_actor_does_not_add_document_recovery_context(question):
    request = _request(question)

    assert recovery_query(request, question) == question
    assert "document_context" not in recovery_query_metadata(request)


@pytest.mark.parametrize("selected", [[], ["paper", "another-paper"]])
def test_generic_type_context_requires_one_selected_or_active_document(selected):
    question = "What type of inflections are considered?"
    request = _request(question, selected_file_ids=selected, active_file_id="")

    assert recovery_query(request, question) == question
    assert "document_context" not in recovery_query_metadata(request)
