from ktem.docqa.claim_filtering import answer_claims, clean_answer_text
from ktem.docqa.qasper_answer_relation import resolve_qasper_answer_relation
from ktem.docqa.qasper_relation_frame import (
    question_relation_frame,
    relation_is_explicit,
)
from ktem.docqa.typed_proposition_authority_schema import exact_slot_set_contract


def test_qasper_drops_empty_formatting_suffix_but_keeps_the_answer_claim():
    answer = "The document-level encoder is novel for document summarization.\n```markdown\n```"

    assert clean_answer_text(answer) == (
        "The document-level encoder is novel for document summarization."
    )
    assert answer_claims(answer) == [
        "The document-level encoder is novel for document summarization."
    ]


def test_qasper_preserves_substantive_formula_table_and_sentence():
    answer = (
        "The reported value is computed from the two inputs.\n"
        "$$ x + y = z $$\n"
        "| year | value |\n| --- | ---: |\n| 2021 | 4 |"
    )

    cleaned = clean_answer_text(answer)

    assert "x + y = z" in cleaned
    assert "| 2021 | 4 |" in cleaned
    assert "computed from the two inputs" in cleaned


def test_qasper_drops_empty_display_block_but_keeps_later_formula():
    answer = "The result is supported.\n$$\n$$\n$$ x + y = z $$"

    assert clean_answer_text(answer) == "The result is supported.\n$$ x + y = z $$"


def test_qasper_relation_frames_cover_novel_baseline_and_improvement():
    cases = (
        (
            "What is novel about their document-level encoder?",
            "novel",
            "The document-level encoder is novel because it represents the whole document.",
        ),
        (
            "What is the baseline for their method?",
            "baseline",
            "The baseline is the previous retrieval method.",
        ),
        (
            "How does their method improve over the baseline?",
            "improve",
            "The method improves the baseline by reducing retrieval errors.",
        ),
    )

    for question, predicate, quote in cases:
        frame = question_relation_frame(question)
        assert frame.predicate == predicate
        assert relation_is_explicit(
            frame,
            quote,
            answer_numbers=set(),
            quote_numbers=set(),
        )


def test_qasper_novel_relation_resolves_against_verified_evidence():
    question = "What is novel about their document-level encoder?"
    answer = "It is novel because it represents the whole document."
    evidence = [
        {
            "evidence_id": "paper-method",
            "source_id": "paper",
            "section_id": "method",
            "text": (
                "The document-level encoder is novel because it represents the "
                "whole document."
            ),
        }
    ]

    resolution = resolve_qasper_answer_relation(question, answer, evidence)

    assert resolution.state == "verified_support"
    assert resolution.atoms


def test_typed_authority_requires_exact_required_verified_and_bound_slot_sets():
    required = ["operand:2017", "operand:2021"]
    bindings = {
        "operand:2017": ("cell:2017",),
        "operand:2021": ("cell:2021",),
    }

    assert exact_slot_set_contract(required, required, bindings)
    assert not exact_slot_set_contract(required, ["operand:2017"], bindings)
    assert not exact_slot_set_contract(
        required,
        required,
        {**bindings, "operand:extra": ("cell:extra",)},
    )
