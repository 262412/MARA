import json
from types import SimpleNamespace

from ktem.reasoning.mara_ragtruth_answering import route_ragtruth_answer
from ktem.reasoning.mara_ragtruth_claims import (
    claim_verifier_response_format,
    heuristic_unsupported_claim_indices,
    response_claims,
    supported_claim_indices,
    unsupported_claim_indices,
)


class _RecordingLLM:
    def __init__(self):
        self.messages = []
        self.kwargs = {}

    def __call__(self, messages, **kwargs):
        self.messages = list(messages)
        self.kwargs = kwargs
        return SimpleNamespace(text='{"hallucination list": ["unsupported span"]}')


class _SequenceLLM:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def __call__(self, messages, **kwargs):
        self.calls.append((list(messages), kwargs))
        return SimpleNamespace(text=next(self.responses))


def _ragtruth_prompt(source: str, response: str) -> str:
    return (
        "/no_think\n"
        "Below is a question:\n"
        "Which exact spans are unsupported?\n\n"
        f"Below are related passages:\n{source}\n\n"
        f"Below is an answer:\n{response}\n\n"
        'Return exactly one JSON object with the key "hallucination list".\n'
        "Answer:"
    )


def test_ragtruth_answering_calls_llm_with_task_prompt_without_retrieved_context():
    llm = _RecordingLLM()
    pipeline = SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    request = SimpleNamespace(
        origin="benchmark",
        verification_domain="ragtruth",
        prompt="RAGTruth source and response contract.",
    )
    bundle = SimpleNamespace(
        items=[{"text": "Retrieved evidence must not be appended."}],
        metadata={},
    )

    answer = route_ragtruth_answer(pipeline, request, bundle)

    assert answer == '{"hallucination list": ["unsupported span"]}'
    assert len(llm.messages) == 2
    assert "conservative hallucination-span evaluator" in llm.messages[0].content
    assert llm.messages[1].content == request.prompt
    assert "Retrieved evidence" not in llm.messages[0].content
    assert "Retrieved evidence" not in llm.messages[1].content
    assert llm.kwargs == {
        "max_tokens": 768,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "ragtruth_hallucination_spans",
                "strict": True,
                "schema": {
                    "type": "object",
                    "properties": {
                        "hallucination list": {
                            "type": "array",
                            "items": {"type": "string"},
                            "maxItems": 8,
                        }
                    },
                    "required": ["hallucination list"],
                    "additionalProperties": False,
                },
            },
        },
        "temperature": 0,
        "top_p": 1,
        "seed": 20260724,
    }
    assert bundle.metadata["generation_contract"] == {
        "temperature": 0,
        "top_p": 1,
        "seed": 20260724,
    }
    assert bundle.metadata["generation_backend"] == "ragtruth_task_llm"


def test_ragtruth_answering_ignores_non_ragtruth_requests():
    answer = route_ragtruth_answer(
        SimpleNamespace(),
        SimpleNamespace(
            origin="benchmark",
            verification_domain="qasper",
            prompt="Question",
        ),
        SimpleNamespace(metadata={}),
    )

    assert answer is None


def test_ragtruth_answering_verifies_claim_indices_and_copies_exact_response_text():
    response = "Sheila accepts a job as a bartender."
    llm = _SequenceLLM(
        [
            '{"hallucination list": []}',
            '{"0":"unsupported"}',
        ]
    )
    pipeline = SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    request = SimpleNamespace(
        origin="benchmark",
        verification_domain="ragtruth",
        prompt=_ragtruth_prompt(
            "Deacon offers Sheila a job as a bartender.",
            response,
        ),
    )
    bundle = SimpleNamespace(items=[], metadata={})

    answer = route_ragtruth_answer(pipeline, request, bundle)

    assert answer is not None
    assert json.loads(answer) == {"hallucination list": [response]}
    assert len(llm.calls) == 2
    assert "offered versus accepted" in llm.calls[1][0][0].content
    assert "[0] Sheila accepts a job as a bartender." in llm.calls[1][0][1].content
    assert llm.calls[1][1]["seed"] == 20260724
    assert bundle.metadata["ragtruth_claim_count"] == 1
    assert bundle.metadata["ragtruth_unsupported_claim_count"] == 1
    assert bundle.metadata["ragtruth_candidate_claim_indices"] == []
    assert bundle.metadata["ragtruth_verifier_unsupported_indices"] == [0]
    assert bundle.metadata["ragtruth_heuristic_unsupported_indices"] == [0]
    assert bundle.metadata["ragtruth_supported_claim_indices"] == []
    assert bundle.metadata["ragtruth_emitted_claim_indices"] == [0]
    assert bundle.metadata["ragtruth_candidate_spans"] == []


def test_ragtruth_answering_filters_near_exact_source_support():
    response = "Bill has passed away."
    llm = _SequenceLLM(
        [
            '{"hallucination list": ["Bill has passed away."]}',
            '{"0":"unsupported"}',
        ]
    )
    pipeline = SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    request = SimpleNamespace(
        origin="benchmark",
        verification_domain="ragtruth",
        prompt=_ragtruth_prompt(
            "A customer wrote that Bill passed away.",
            response,
        ),
    )
    bundle = SimpleNamespace(items=[], metadata={})

    answer = route_ragtruth_answer(pipeline, request, bundle)

    assert answer is not None
    assert json.loads(answer) == {"hallucination list": []}
    assert bundle.metadata["ragtruth_supported_span_filter_count"] == 1


def test_ragtruth_claim_schema_requires_one_verdict_for_every_claim():
    schema = claim_verifier_response_format(3)
    object_schema = schema["json_schema"]["schema"]

    assert object_schema["properties"] == {
        "0": {"type": "string", "enum": ["supported", "unsupported"]},
        "1": {"type": "string", "enum": ["supported", "unsupported"]},
        "2": {"type": "string", "enum": ["supported", "unsupported"]},
    }
    assert object_schema["required"] == ["0", "1", "2"]
    assert object_schema["additionalProperties"] is False


def test_ragtruth_claim_verdict_parser_returns_only_unsupported_indices():
    assert unsupported_claim_indices(
        '{"0":"supported","1":"unsupported","2":"supported"}',
        3,
    ) == {1}


def test_ragtruth_claim_splitter_drops_standalone_list_markers():
    assert response_claims(
        "Foods include:\n\n1. Apples are high in fiber.\n2. Fish contains oil."
    ) == [
        "Foods include:",
        "Apples are high in fiber.",
        "Fish contains oil.",
    ]


def test_ragtruth_structured_support_filters_bound_fields_and_review_facts():
    source = str(
        {
            "name": "Surf Dog",
            "business_stars": 5.0,
            "attributes": {
                "Ambience": {
                    "touristy": True,
                    "classy": True,
                    "romantic": False,
                    "trendy": False,
                }
            },
            "review_info": [
                {
                    "review_text": (
                        "So sorry to hear Bill passed away. He was kind and thoughtful."
                    )
                },
                {
                    "review_text": (
                        "AN OASIS. Don't drive by without stopping. "
                        "Seal Rookery down the trail."
                    )
                },
            ],
        }
    )
    claims = [
        "The restaurant has an average rating of 5 stars.",
        "Bill has passed away and was described as kind and thoughtful.",
        "The location is near the Seal Rookery, adding to its appeal.",
        (
            "The restaurant's ambiance is touristy and classy, but not "
            "romantic or trendy."
        ),
        "Most dishes fall in the $15-$30 range.",
    ]

    assert supported_claim_indices(source, claims) == {0, 1, 2, 3}


def test_ragtruth_structured_support_does_not_hide_relation_changes():
    source = str(
        {"review_info": [{"review_text": "Deacon offers Sheila a job as a bartender."}]}
    )

    assert (
        supported_claim_indices(
            source,
            ["Sheila accepts a job as a bartender."],
        )
        == set()
    )


def test_ragtruth_heuristic_flags_directional_relation_changes():
    source = "Deacon offers Sheila a job as a bartender."
    claims = ["Sheila accepts a job as a bartender."]

    assert heuristic_unsupported_claim_indices(source, claims) == {0}


def test_ragtruth_structured_support_handles_review_paraphrases_and_intros():
    source = str(
        {
            "name": "Surf Dog",
            "review_info": [
                {
                    "review_text": (
                        "So sorry to hear Bill passed away. "
                        "He was the nicest man, kind and thoughtful."
                    )
                },
                {
                    "review_text": (
                        "AN OASIS. Don't drive by without stopping. "
                        "Seal Rookery down the trail."
                    )
                },
            ],
        }
    )
    claims = [
        (
            "Unfortunately, it seems that Bill has passed away, as mentioned "
            "in another review where a customer expresses their sadness and "
            "describes him as a kind and thoughtful man."
        ),
        (
            "The restaurant is described as an oasis, and customers are "
            "encouraged not to drive by without stopping."
        ),
    ]
    passage_source = str(
        {
            "question": "How do I level a mailbox post?",
            "passages": "Use a post level to hold the mailbox post plumb.",
        }
    )

    assert supported_claim_indices(source, claims) == {0, 1}
    assert supported_claim_indices(
        passage_source,
        ["To level a mailbox post, follow these steps:"],
    ) == {0}


def test_ragtruth_passage_novelty_detector_finds_new_properties_only():
    source = str(
        {
            "question": "diet to help raise hdl levels",
            "passages": (
                "Good ones are colorful bell peppers, chili peppers, and "
                "broccoli. Foods high in soluble fiber may boost HDL levels."
            ),
        }
    )
    claims = [
        (
            "Bell peppers, chili peppers, and broccoli - These vegetables are "
            "rich in antioxidants and vitamins that can help raise HDL levels."
        ),
        "Foods high in soluble fiber may boost HDL levels.",
        "Unable to answer based on given passages.",
    ]

    assert heuristic_unsupported_claim_indices(source, claims) == {0}


def test_ragtruth_passage_mapping_flattens_exact_supported_sentences():
    source = str(
        {
            "question": "How do I find a Nike style number?",
            "passages": (
                "The product's style number will be on the right-hand side of "
                "its page. The number will usually be five or six digits, "
                "followed by a dash, then another number for its color code."
            ),
        }
    )

    assert supported_claim_indices(
        source,
        [
            (
                "It is usually five or six digits, followed by a dash and "
                "another number indicating the color code."
            )
        ],
    ) == {0}


def test_ragtruth_requires_detector_agreement_for_noncontradictory_claim():
    response = "Bananas are yellow."
    llm = _SequenceLLM(
        [
            '{"hallucination list": ["Bananas are yellow."]}',
            '{"0":"supported"}',
        ]
    )
    pipeline = SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    request = SimpleNamespace(
        origin="benchmark",
        verification_domain="ragtruth",
        prompt=_ragtruth_prompt("Apples are fruit.", response),
    )
    bundle = SimpleNamespace(items=[], metadata={})

    answer = route_ragtruth_answer(pipeline, request, bundle)

    assert answer is not None
    assert json.loads(answer) == {"hallucination list": []}


def test_ragtruth_deterministic_relation_conflict_does_not_require_llm_agreement():
    response = "Sheila accepts a job as a bartender."
    llm = _SequenceLLM(
        [
            '{"hallucination list": []}',
            '{"0":"supported"}',
        ]
    )
    pipeline = SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    request = SimpleNamespace(
        origin="benchmark",
        verification_domain="ragtruth",
        prompt=_ragtruth_prompt(
            "Deacon offers Sheila a job as a bartender.",
            response,
        ),
    )
    bundle = SimpleNamespace(items=[], metadata={})

    answer = route_ragtruth_answer(pipeline, request, bundle)

    assert answer is not None
    assert json.loads(answer) == {"hallucination list": [response]}


def test_ragtruth_data2txt_accepts_structured_verifier_without_first_detector():
    response = "Cafe Example has a Michelin star."
    prompt = (
        "/no_think\n"
        "Below is the structured JSON data:\n"
        "{'name': 'Cafe Example'}\n\n"
        "Below is an overview of the data:\n"
        f"{response}\n\n"
        'Return exactly one JSON object with the key "hallucination list".\n'
        "Answer:"
    )
    llm = _SequenceLLM(
        [
            '{"hallucination list": []}',
            '{"0":"unsupported"}',
        ]
    )
    pipeline = SimpleNamespace(answering_pipeline=SimpleNamespace(llm=llm))
    request = SimpleNamespace(
        origin="benchmark",
        verification_domain="ragtruth",
        prompt=prompt,
    )
    bundle = SimpleNamespace(items=[], metadata={})

    answer = route_ragtruth_answer(pipeline, request, bundle)

    assert answer is not None
    assert json.loads(answer) == {"hallucination list": [response]}
