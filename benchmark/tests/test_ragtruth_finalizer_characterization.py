import json

import pytest

from benchmark.ragtruth_answer_finalizer import finalize_ragtruth_if_requested


def test_ragtruth_finalizer_normalizes_valid_contract_answer():
    raw_answer = (
        "The response contains unsupported details.\n\n"
        "```json\n"
        '{"hallucination list": ["profit doubled"]}\n'
        "```"
    )

    normalized = finalize_ragtruth_if_requested(raw_answer, "RAGTruth-plan5")

    assert normalized == '{"hallucination list": ["profit doubled"]}'
    assert set(json.loads(normalized)) == {"hallucination list"}


def test_ragtruth_finalizer_preserves_repaired_span_text():
    normalized = finalize_ragtruth_if_requested(
        "{'hallucination list': ['profit doubled']}",
        "ragtruth",
    )

    assert json.loads(normalized) == {"hallucination list": ["profit doubled"]}


@pytest.mark.parametrize(
    "raw_answer",
    (
        "The response is fully supported.",
        '{"hallucination list": ["valid span", 1]}',
        '{"answer": "valid span"}',
    ),
)
def test_ragtruth_finalizer_returns_empty_error_result_for_invalid_contract(
    raw_answer: str,
):
    assert finalize_ragtruth_if_requested(raw_answer, "ragtruth") == ""


def test_ragtruth_finalizer_is_a_noop_for_other_datasets():
    raw_answer = "The answer is unchanged for ALCE."

    assert finalize_ragtruth_if_requested(raw_answer, "alce") == raw_answer
