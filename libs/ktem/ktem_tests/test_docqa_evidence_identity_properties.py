from itertools import product

from hypothesis import given, settings
from hypothesis import strategies as st
from ktem.docqa.evidence_identity import (
    canonicalize_and_dedupe_evidence,
    exact_evidence_aliases,
    identity_of,
)

_IDENTIFIER = st.text(
    alphabet=st.characters(
        whitelist_categories=("Ll", "Lu"),
        whitelist_characters="0123456789-_",
    ),
    min_size=1,
    max_size=24,
).filter(lambda value: value.strip("-_"))


def test_atomic_identity_is_injective_across_sources_kinds_and_local_ids():
    identities = {
        identity_of(
            {
                "source_id": source,
                identity_field: local_id,
                "evidence_level": evidence_level,
            }
        ).key
        for source, (identity_field, evidence_level), local_id in product(
            ("document-a", "document-b"),
            (
                ("cell_id", "cell"),
                ("span_id", "span"),
                ("element_id", "element"),
            ),
            ("atom-1", "atom-2"),
        )
    }

    assert len(identities) == 12


def test_sibling_cells_never_share_an_exact_join_alias():
    siblings = [
        {
            "source_id": "report",
            "evidence_id": "parent-table",
            "element_id": "parent-table",
            "cell_id": f"revenue-{year}",
            "evidence_level": "cell",
        }
        for year in range(2018, 2025)
    ]

    for index, left in enumerate(siblings):
        for right in siblings[index + 1 :]:
            assert exact_evidence_aliases(left).isdisjoint(
                exact_evidence_aliases(right)
            )


def test_multitable_multiyear_identity_round_trip_has_no_collision():
    atoms = [
        {
            "source_id": source,
            "source_aliases": [f"{source}.pdf"],
            "evidence_id": table,
            "element_id": table,
            "table_id": table,
            "cell_id": f"{table}:{row}:{year}",
            "row_label": row,
            "period": year,
            "continuation_id": f"{table}:continuation",
            "evidence_level": "cell",
            "text": f"{row} {year}",
        }
        for source, table, row, year in product(
            ("document-a", "document-b"),
            ("income", "balance"),
            ("revenue", "profit"),
            ("2023", "2024"),
        )
    ]

    deduped, trace = canonicalize_and_dedupe_evidence(atoms)

    assert len(deduped) == len(atoms)
    assert trace["output_count"] == len(atoms)
    assert len({identity_of(item).key for item in deduped}) == len(atoms)


@settings(max_examples=100)
@given(source=_IDENTIFIER, cell=_IDENTIFIER, alias=_IDENTIFIER)
def test_cell_identity_is_stable_across_source_aliases(
    source: str,
    cell: str,
    alias: str,
):
    plain = {"source_id": source, "cell_id": cell}
    aliased = {
        "source_id": source,
        "source_aliases": [alias, f"{source}.pdf"],
        "cell_id": cell,
    }

    assert identity_of(plain) == identity_of(aliased)


@settings(max_examples=100)
@given(
    source=_IDENTIFIER,
    table=_IDENTIFIER,
    row=st.integers(min_value=0, max_value=1000),
    column=st.integers(min_value=0, max_value=1000),
)
def test_nested_metadata_and_top_level_fields_share_identity(
    source: str,
    table: str,
    row: int,
    column: int,
):
    top_level = {
        "source_id": source,
        "table_id": table,
        "row_index": row,
        "column_index": column,
    }
    nested = {
        "metadata": {
            "source_id": source,
            "table_id": table,
            "row_index": row,
            "column_index": column,
        }
    }

    assert identity_of(top_level) == identity_of(nested)


@settings(max_examples=100)
@given(
    source=_IDENTIFIER,
    page=st.integers(min_value=1, max_value=500),
    start=st.integers(min_value=0, max_value=100_000),
    length=st.integers(min_value=1, max_value=10_000),
)
def test_chunk_range_round_trip_is_stable(
    source: str,
    page: int,
    start: int,
    length: int,
):
    item = {
        "source_id": source,
        "page_label": str(page),
        "chunk_start": start,
        "chunk_end": start + length,
        "text": "chunk",
    }
    canonical, _trace = canonicalize_and_dedupe_evidence([item])

    assert identity_of(canonical[0]) == identity_of(item)


@settings(max_examples=100)
@given(
    source=_IDENTIFIER,
    evidence_id=_IDENTIFIER,
    first=_IDENTIFIER,
    second=_IDENTIFIER,
)
def test_representation_order_does_not_change_identity_or_content(
    source: str,
    evidence_id: str,
    first: str,
    second: str,
):
    representations = [
        {"modality": "ocr", "text": first},
        {"modality": "vlm", "text": second},
    ]
    left, _trace = canonicalize_and_dedupe_evidence(
        [
            {
                "source_id": source,
                "evidence_id": evidence_id,
                "representations": representations,
            }
        ]
    )
    right, _trace = canonicalize_and_dedupe_evidence(
        [
            {
                "source_id": source,
                "evidence_id": evidence_id,
                "representations": list(reversed(representations)),
            }
        ]
    )

    assert identity_of(left[0]) == identity_of(right[0])
    assert {
        (item["modality"], item["text"]) for item in left[0]["representations"]
    } == {(item["modality"], item["text"]) for item in right[0]["representations"]}


@settings(max_examples=100)
@given(
    source=_IDENTIFIER,
    continuation=_IDENTIFIER,
    page=st.integers(min_value=1, max_value=500),
    coordinates=st.tuples(
        st.integers(min_value=0, max_value=10_000),
        st.integers(min_value=0, max_value=10_000),
        st.integers(min_value=0, max_value=10_000),
        st.integers(min_value=0, max_value=10_000),
    ),
)
def test_bbox_quantization_and_continuation_round_trip(
    source: str,
    continuation: str,
    page: int,
    coordinates: tuple[int, int, int, int],
):
    bbox = [coordinate / 10 for coordinate in coordinates]
    canonical, _trace = canonicalize_and_dedupe_evidence(
        [
            {
                "source_id": source,
                "page_label": str(page),
                "bbox": bbox,
                "continuation_id": continuation,
                "text": "located evidence",
            }
        ]
    )

    assert canonical[0]["continuation_id"] == continuation
    assert identity_of(canonical[0]) == identity_of(
        {
            "source_id": source,
            "page_label": str(page),
            "bbox": bbox,
        }
    )
