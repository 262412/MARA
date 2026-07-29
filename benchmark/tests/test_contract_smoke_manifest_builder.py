from __future__ import annotations

from pypdf import PdfReader

from scripts.slurm import build_contract_smoke_manifests as builder


def test_contract_smoke_case_sets_cover_requested_contracts():
    assert len(builder.FINANCE_CASES) == 4
    assert len(builder.QASPER_CASES) == 4
    assert set().union(
        *builder.FINANCE_CASES.values(),
        builder.FINANCE_NEGATIVE_REQUIREMENTS,
    ) == {
        "same_parent_distinct_year_cells",
        "materialized_parent_operand",
        "header_or_caption_dimension",
        "multi_period_percentage_change",
        "missing_execution_requirement_abstains",
    }
    assert set().union(
        *builder.QASPER_CASES.values(),
        builder.QASPER_SYNTHETIC_REQUIREMENTS,
    ) == {
        "ordinary_free_text",
        "yes_no",
        "support_and_contradiction",
        "cross_page_required_slots",
        "answerability_rewrite",
    }


def test_contract_smoke_route_forces_hybrid_strict_verification():
    route = builder.contract_route(verification_domain="finance")

    assert route["route_policy"] == "hybrid"
    assert route["allowed_routes"] == ["hybrid"]
    assert route["verification_mode"] == "strict"
    assert route["verification_domain"] == "finance"
    assert route["headline_role"] == "deployed_policy"


def test_qasper_cross_page_fixture_is_a_legible_two_page_pdf(tmp_path):
    output = tmp_path / "qasper-cross-page.pdf"

    builder.write_qasper_cross_page_pdf(output)

    reader = PdfReader(output)
    assert len(reader.pages) == 2
    assert "released the code publicly" in (reader.pages[0].extract_text() or "")
    assert "did not release the code" in (reader.pages[1].extract_text() or "")


def test_finance_smoke_uses_audited_fixed_page_mapping():
    example = {
        "document_id": "ADOBE_2016_10K",
        "document_ids": ["ADOBE_2016_10K"],
        "evidence_pages": [61],
        "evidence_sources": ["ADOBE_2016_10K#page:61"],
        "gold_evidence": [
            {
                "document_id": "ADOBE_2016_10K",
                "page": 61,
                "citation": "ADOBE_2016_10K#page:61",
            }
        ],
    }

    mapped = builder.with_audited_finance_page_mappings(example)

    assert mapped["evidence_pages"] == [62]
    assert mapped["gold_evidence"][0]["dataset_page"] == 61
    assert mapped["gold_evidence"][0]["page"] == 62
    assert mapped["gold_evidence"][0]["page_mapping"] == {
        "dataset_page": 61,
        "runtime_page": 62,
        "mapping_source": "financebench_contract_fixed_mapping",
        "mapping_confidence": 1.0,
        "mapping_version": "financebench_contract_page_mapping.v1",
    }
