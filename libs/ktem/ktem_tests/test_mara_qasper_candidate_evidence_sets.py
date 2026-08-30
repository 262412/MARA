from __future__ import annotations

from typing import Any

from ktem.docqa.qasper_semantic_pack_contract import canonical_payload_digest
from ktem.docqa.question_proposition import build_question_proposition
from ktem.docqa.semantic_relation_clause_lexical import semantic_content_token_set
from ktem.reasoning.mara_qasper_candidate_evidence_sets import (  # type: ignore[attr-defined]
    candidate_span_set,
    enumerate_candidate_span_sets,
)

QUESTION = "Did the authors compare the two systems?"
REQUIRED_SLOTS = ("actor", "predicate", "object", "quantifier")


def _selector(
    selector_id: str,
    text: str,
    start: int,
    *,
    event_id: str,
    slots: tuple[str, ...],
    predicate_match_kind: str = "exact",
    relation_state: str = "affirmative_assertion",
    alignment_status: str = "verified",
) -> dict[str, Any]:
    selector = {
        "evidence_id": "paper",
        "selector_id": selector_id,
        "text": text,
        "span_start": start,
        "span_end": start + len(text),
        "event_id": event_id,
        "slot_hints": list(slots),
        "object_tokens": sorted(semantic_content_token_set(text)),
        "predicate_match_kind": predicate_match_kind,
        "relation_bearing": True,
        "local_relation_state": relation_state,
    }
    alignment = {
        "contract_id": "qasper_selector_semantic_alignment.v1",
        "status": alignment_status,
        "proposition_id": build_question_proposition(QUESTION).proposition_id,
        "evidence_id": selector["evidence_id"],
        "selector_id": selector["selector_id"],
        "span_start": selector["span_start"],
        "span_end": selector["span_end"],
        "text_digest": canonical_payload_digest(text),
        "event_id": event_id,
        "slot_refs": {slot: selector_id for slot in slots},
        "required_object_tokens": sorted(
            semantic_content_token_set(
                build_question_proposition(QUESTION).object_surface
            )
        ),
        "covered_object_tokens": sorted(
            semantic_content_token_set(text)
            & semantic_content_token_set(
                build_question_proposition(QUESTION).object_surface
            )
        ),
        "predicate_concept": build_question_proposition(QUESTION).predicate,
        "predicate_match_kind": predicate_match_kind,
        "polarity_relation": "proposition_support",
        "local_relation_state": relation_state,
    }
    selector["semantic_alignment"] = {
        **alignment,
        "alignment_digest": canonical_payload_digest(alignment),
    }
    return selector


def test_selector_enumerates_ranked_alternatives_and_preserves_span_identity() -> None:
    selectors = [
        _selector(
            "A:S1",
            "The authors compared the two systems",
            0,
            event_id="event-a",
            slots=REQUIRED_SLOTS,
        ),
        _selector(
            "Z:S1",
            "The authors compared",
            100,
            event_id="event-z",
            slots=("actor", "predicate"),
        ),
        _selector(
            "Z:S2",
            "the two systems",
            130,
            event_id="event-z",
            slots=("object", "quantifier"),
        ),
    ]

    alternatives = enumerate_candidate_span_sets(
        QUESTION,
        selectors,
        REQUIRED_SLOTS,
        polarity="yes",
    )

    assert len(alternatives) >= 2
    identities = {
        tuple(
            (value["evidence_id"], value["selector_id"], value["event_id"])
            for value in alternative
        )
        for alternative in alternatives
    }
    assert {
        ("paper", "A:S1", "event-a"),
    } in identities
    assert {
        ("paper", "Z:S1", "event-z"),
        ("paper", "Z:S2", "event-z"),
    } in identities

    selected = candidate_span_set(
        QUESTION,
        list(reversed(selectors)),
        REQUIRED_SLOTS,
        polarity="yes",
    )
    assert selected is not None
    assert all(
        {
            "evidence_id",
            "selector_id",
            "event_id",
            "span_start",
            "span_end",
        }
        <= set(value)
        for value in selected
    )
    assert tuple(value["selector_id"] for value in selected) == tuple(
        value["selector_id"] for value in alternatives[0]
    )


def test_unattested_predicate_paraphrase_cannot_be_promoted_to_authority() -> None:
    selector = _selector(
        "P:S1",
        "The study juxtaposed the two systems",
        17,
        event_id="event-paraphrase",
        slots=REQUIRED_SLOTS,
        predicate_match_kind="paraphrase",
    )
    selector.pop("semantic_alignment")

    assert (
        candidate_span_set(
            QUESTION,
            [selector],
            REQUIRED_SLOTS,
            polarity="yes",
        )
        is None
    )


def test_audited_paraphrase_binds_exact_local_span_and_event() -> None:
    selector = _selector(
        "P:S1",
        "The study juxtaposed the two systems",
        17,
        event_id="event-paraphrase",
        slots=REQUIRED_SLOTS,
        predicate_match_kind="paraphrase",
    )

    selected = candidate_span_set(
        QUESTION,
        [selector],
        REQUIRED_SLOTS,
        polarity="yes",
    )

    assert selected is not None
    assert [
        (value["selector_id"], value["event_id"], value["span_start"])
        for value in selected
    ] == [("P:S1", "event-paraphrase", 17)]
    alignment = selected[0]["semantic_alignment"]
    assert (
        alignment["proposition_id"]
        == build_question_proposition(QUESTION).proposition_id
    )
    assert alignment["text_digest"] == canonical_payload_digest(selected[0]["text"])
    assert alignment["alignment_digest"] == canonical_payload_digest(
        {key: value for key, value in alignment.items() if key != "alignment_digest"}
    )
