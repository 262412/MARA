from __future__ import annotations

import pytest
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.query_planning import bind_evidence_slots, build_query_plan

QUESTION = "Across pages 1 and 2, did the authors release the code?"


def _page(
    evidence_id: str,
    page_label: str,
    text: str,
    *,
    modality: str = "image",
    evidence_level: str = "page",
    section_id: str = "",
) -> dict[str, str]:
    return {
        "evidence_id": evidence_id,
        "source_id": "paper",
        "page_label": page_label,
        "modality": modality,
        "evidence_level": evidence_level,
        "section_id": section_id,
        "text": text,
    }


def _bound(items: list[dict[str, str]]):
    return bind_evidence_slots(
        build_query_plan(
            QUESTION,
            answer_type="boolean",
            verification_domain="qasper",
        ),
        items,
    )


@pytest.mark.parametrize(
    ("second_text", "second_section"),
    (
        ("The authors evaluated the code on Page 2.", "results"),
        ("The authors released the dataset on Page 2.", "results"),
        ("Smith et al. did not release the code on Page 2.", "related_work"),
        ("Page 2", "results"),
    ),
)
def test_composite_proposition_rejects_invalid_second_page(
    second_text: str,
    second_section: str,
) -> None:
    page_1 = _page(
        "page-1",
        "1",
        "The authors released the code publicly with the paper. Page 1",
        section_id="methods",
    )
    page_2 = _page(
        "page-2",
        "2",
        second_text,
        section_id=second_section,
    )

    proposition, left, right = _bound([page_1, page_2]).evidence_slots

    assert left.evidence_ids == (identity_of(page_1).key,)
    assert right.evidence_ids == (identity_of(page_2).key,)
    assert proposition.status == "missing"
    assert proposition.evidence_ids == ()


def test_composite_proposition_rejects_duplicate_canonical_identity() -> None:
    page_1 = _page(
        "duplicated",
        "1",
        "The authors released the code. Page 1",
    )
    page_2 = _page(
        "duplicated",
        "2",
        "The authors did not release the code. Page 2",
    )

    proposition, _left, right = _bound([page_1, page_2]).evidence_slots

    assert right.status == "missing"
    assert proposition.status == "missing"
    assert proposition.evidence_ids == ()


def test_composite_proposition_rejects_graph_copy_as_page_authority() -> None:
    page_1 = _page(
        "page-1",
        "1",
        "The authors released the code. Page 1",
    )
    graph_page_2 = _page(
        "graph-page-2",
        "2",
        "The authors did not release the code.",
        modality="graph",
        evidence_level="graph",
    )

    proposition, _left, right = _bound([page_1, graph_page_2]).evidence_slots

    assert right.evidence_ids == (identity_of(graph_page_2).key,)
    assert proposition.status == "missing"
    assert proposition.evidence_ids == ()


def test_same_polarity_pages_are_authoritative_without_implying_conflict() -> None:
    page_1 = _page(
        "page-1",
        "1",
        "The authors released the code with the paper. Page 1",
    )
    page_2 = _page(
        "page-2",
        "2",
        "The authors also released the code for the final system. Page 2",
    )

    proposition, _left, _right = _bound([page_1, page_2]).evidence_slots

    assert proposition.status == "retrieved_unverified"
    assert proposition.evidence_ids == (
        identity_of(page_1).key,
        identity_of(page_2).key,
    )
