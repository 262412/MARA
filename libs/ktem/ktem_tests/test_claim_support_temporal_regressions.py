from __future__ import annotations

from ktem.docqa.claim_support import claim_supported, text_contradicts_claim


def test_mixed_multi_year_chunk_does_not_turn_exact_temporal_support_into_conflict():
    claim = (
        'The original artist of "The Sound of Silence," the song released in '
        "1964, is Simon & Garfunkel."
    )
    evidence = {
        "evidence_id": "sound-of-silence",
        "source_id": "music-history",
        "text": (
            '"The Sound of Silence" is a song by Simon & Garfunkel. '
            "The song was recorded in March 1964. "
            "Electric overdubs were recorded in 1965, the album was released "
            "in 1966, and a cover version was released in 2015."
        ),
    }

    assert text_contradicts_claim(claim, evidence["text"]) is False
    assert claim_supported(claim, [evidence]) is True


def test_single_same_fact_conflicting_year_remains_a_contradiction():
    claim = "The report was published in 2020."
    evidence = "The same report was published in 2021."

    assert text_contradicts_claim(claim, evidence) is True
