from itertools import product

from ktem.docqa.evidence_identity import (
    canonicalize_and_dedupe_evidence,
    exact_evidence_aliases,
    identity_of,
)


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
