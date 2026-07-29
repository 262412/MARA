from __future__ import annotations

from ktem.docqa.benchmark_evidence import benchmark_evidence_record
from ktem.docqa.evidence_identity import identity_of
from ktem.docqa.evidence_item_coercion import coerce_item

from benchmark.contract_invariant_metrics import contract_invariant_summary


def _cell(row_label: str, *, value: str = "100") -> dict[str, object]:
    return {
        "source_id": "report",
        "page_label": "1",
        "table_id": "table",
        "cell_id": "revenue-2022",
        "evidence_level": "cell",
        "row_label": row_label,
        "column_label": "FY\u00a02022 ",
        "period": "2022",
        "value": value,
        "text": f"{row_label} {value}",
    }


def test_nbsp_and_trailing_space_are_roundtrip_equivalent():
    summary = contract_invariant_summary(
        [
            {
                "evidence_metadata": {
                    "canonical_candidate_evidence": [
                        coerce_item(_cell("Operating income\u00a0 "))
                    ]
                }
            }
        ]
    )

    assert summary["normalized_label_roundtrip"] == 1.0
    assert summary["normalization_equivalence_count"] == 2.0


def test_internal_unicode_whitespace_is_normalized():
    item = coerce_item(_cell("Operating\u2003income"))

    assert item["row_label"] == "Operating income"
    assert item["normalized_row_label"] == "Operating income"


def test_numeric_value_is_not_whitespace_normalized_semantically():
    item = coerce_item(_cell("Revenue\u00a0", value="1\u00a0000"))
    projected = benchmark_evidence_record(item).as_dict()

    assert item["value"] == "1\u00a0000"
    assert projected["value"] == "1\u00a0000"


def test_identity_is_not_changed_by_label_normalization():
    raw = _cell("Operating\u2003income\u00a0")
    coerced = coerce_item(raw)

    assert identity_of(raw) == identity_of(coerced)


def test_raw_representation_preserves_original_nbsp():
    item = coerce_item(_cell("Operating income\u00a0 "))
    projected = benchmark_evidence_record(item).as_dict()

    assert item["raw_row_label"] == "Operating income\u00a0 "
    assert projected["raw_row_label"] == "Operating income\u00a0 "


def test_true_label_change_still_fails_roundtrip():
    item = coerce_item(_cell("Revenue"))
    item["normalized_row_label"] = "Operating income"
    summary = contract_invariant_summary(
        [{"evidence_metadata": {"canonical_candidate_evidence": [item]}}]
    )

    assert summary["normalized_label_roundtrip"] == 0.0
