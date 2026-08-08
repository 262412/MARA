from dataclasses import dataclass
from typing import Any

from benchmark.alce_answer_grounding import (
    ALCE_MAX_GROUNDING_PROMPT_CHARS,
    apply_alce_answer_grounding,
    ground_alce_short_answer,
)


@dataclass
class _Response:
    text: str


class _LLM:
    def __init__(self, answer: str) -> None:
        self.answer = answer
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def __call__(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        return _Response(self.answer)


def test_alce_grounding_rejects_unsafe_correction_of_nonempty_candidate():
    llm = _LLM('{"verdict":"corrected","answer":"John Boehner","evidence_index":0}')

    result = ground_alce_short_answer(
        llm,
        question=(
            "Who was the US Speaker for the House of Representatives from "
            "January 6, 2015 to October 29, 2015?"
        ),
        candidate_answer="Paul Ryan",
        evidence_items=[
            {
                "evidence_id": "speaker-range",
                "text": (
                    "From January 6, 2015 to October 29, 2015, John Boehner "
                    "was the Speaker of the US House."
                ),
            }
        ],
    )

    assert result.answer == "Paul Ryan"
    assert result.trace == {
        "contract_id": "alce_short_answer_grounding.v2",
        "status": "rejected_unsafe_correction",
        "verdict": "corrected",
        "evidence_id": "speaker-range",
        "answer_changed": False,
        "generation_contract": {
            "temperature": 0,
            "top_p": 1,
            "seed": 20260724,
        },
    }
    assert llm.calls[0][1]["temperature"] == 0
    assert llm.calls[0][1]["top_p"] == 1
    assert llm.calls[0][1]["seed"] == 20260724
    assert llm.calls[0][1]["response_format"]["type"] == "json_schema"


def test_alce_grounding_recovers_false_unanswerable_from_direct_evidence():
    llm = _LLM(
        '{"verdict":"corrected","answer":"October 20, 2017",' '"evidence_index":0}'
    )

    result = ground_alce_short_answer(
        llm,
        question="When does episode 36 of Stuck in the Middle air?",
        candidate_answer="unanswerable",
        evidence_items=[
            {
                "evidence_id": "episode-36",
                "text": "Episode 36 aired on October 20, 2017.",
            }
        ],
    )

    assert result.answer == "October 20, 2017"
    assert result.trace["answer_changed"] is True


def test_alce_grounding_preserves_nonempty_candidate_on_insufficient_verdict():
    llm = _LLM('{"verdict":"insufficient_evidence","answer":"","evidence_index":-1}')

    result = ground_alce_short_answer(
        llm,
        question="Who was Speaker?",
        candidate_answer="John Boehner",
        evidence_items=[
            {
                "evidence_id": "speaker",
                "text": "John Boehner was Speaker.",
            }
        ],
    )

    assert result.answer == "John Boehner"
    assert result.trace["status"] == "advisory_insufficient_evidence"
    assert result.trace["answer_changed"] is False


def test_alce_supported_verdict_cannot_rewrite_candidate():
    llm = _LLM('{"verdict":"supported","answer":"Paul Ryan","evidence_index":0}')

    result = ground_alce_short_answer(
        llm,
        question="Who was Speaker?",
        candidate_answer="John Boehner",
        evidence_items=[
            {
                "evidence_id": "speaker",
                "text": "John Boehner and Paul Ryan both served as Speaker.",
            }
        ],
    )

    assert result.answer == "John Boehner"
    assert result.trace["status"] == "rejected_inconsistent_supported_answer"
    assert result.trace["answer_changed"] is False


def test_alce_grounding_rejects_correction_not_traceable_to_selected_evidence():
    llm = _LLM('{"verdict":"corrected","answer":"Paul Ryan","evidence_index":0}')

    result = ground_alce_short_answer(
        llm,
        question="Who was Speaker during the specified period?",
        candidate_answer="John Boehner",
        evidence_items=[
            {
                "evidence_id": "speaker-range",
                "text": "John Boehner was Speaker during the specified period.",
            }
        ],
    )

    assert result.answer == "John Boehner"
    assert result.trace["status"] == "rejected_ungrounded_answer"
    assert result.trace["answer_changed"] is False


def test_alce_grounding_falls_back_without_parseable_schema_output():
    llm = _LLM("John Boehner")

    result = ground_alce_short_answer(
        llm,
        question="Who was Speaker?",
        candidate_answer="John Boehner",
        evidence_items=[
            {
                "evidence_id": "speaker",
                "text": "John Boehner was Speaker.",
            }
        ],
    )

    assert result.answer == "John Boehner"
    assert result.trace["status"] == "error"


def test_alce_grounding_wrapper_only_loads_llm_for_alce_asqa():
    calls = []

    answer, trace, seconds = apply_alce_answer_grounding(
        suite_name="financebench",
        llm_factory=lambda: calls.append("loaded"),
        question="Who was Speaker?",
        candidate_answer="John Boehner",
        evidence_items=[],
    )

    assert answer == "John Boehner"
    assert trace == {}
    assert seconds == 0
    assert calls == []


def test_alce_grounding_prompt_reserves_context_budget():
    llm = _LLM('{"verdict":"supported","answer":"John Boehner","evidence_index":0}')

    ground_alce_short_answer(
        llm,
        question="Who was Speaker?",
        candidate_answer="John Boehner",
        evidence_items=[
            {
                "evidence_id": f"evidence-{index}",
                "text": ("long evidence sentence " * 200),
            }
            for index in range(8)
        ],
    )

    assert len(llm.calls[0][0]) <= ALCE_MAX_GROUNDING_PROMPT_CHARS
    assert llm.calls[0][1]["max_tokens"] == 192
