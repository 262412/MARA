from types import SimpleNamespace

from ktem.reasoning.mara_controller_request import controller_execution_request


def test_controller_request_propagates_answer_type_for_query_planning():
    pipeline = SimpleNamespace(
        task_type="numeric",
        dataset_family="finance",
        controller_question="What was the percentage change?",
        retrieval_query="percentage change",
        docqa_request=SimpleNamespace(origin="benchmark"),
    )

    request = controller_execution_request(pipeline, "Generate the final answer.")

    assert request.task_type == "numeric"
    assert request.answer_type == "numeric"
