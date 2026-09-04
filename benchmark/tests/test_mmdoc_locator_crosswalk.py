from __future__ import annotations

from copy import deepcopy
from typing import Any

from benchmark.element_locator_metrics import element_locator_hit_score
from benchmark.metrics import element_hit_score
from benchmark.mmdoc_locator_crosswalk import apply_mmdoc_locator_crosswalk
from benchmark.page_metric_contract import page_metric_contract
from benchmark.stage_metrics import (
    prediction_stage_metric_status,
    prediction_stage_metrics,
)

VALUES = {
    "2017": "1082.4",
    "2018": "1200.0",
    "2019": "1186.7",
    "2020": "810.8",
    "2021": "921.0",
}


def _gold_evidence() -> list[dict[str, Any]]:
    return [
        {
            "source_id": "NYSE_TM_2021",
            "page": 34,
            "element_id": "image5",
            "element_type": "table",
            "citation": "NYSE_TM_2021#page:34",
            "image_quote": (
                "Total Shareholder Return fiscal years 2017 1082.4 "
                "2018 1200.0 2019 1186.7 2020 810.8 2021 921.0"
            ),
        }
    ]


def _runtime_cells() -> list[dict[str, Any]]:
    return [
        {
            "evidence_id": f"cell:{year}",
            "source_id": "NYSE_TM_2021",
            "file_id": "NYSE_TM_2021",
            "page_label": "35",
            "element_type": "table",
            "modality": "table",
            "evidence_level": "cell",
            "cell_id": f"vertical-table-35-1-35:cell:1:{index}",
            "row_label": "Total shareholder return*2",
            "column_label": year,
            "period": year,
            "value": value,
            "text": f"Total shareholder return*2 {year} {value}",
        }
        for index, (year, value) in enumerate(VALUES.items(), start=1)
    ]


def _prediction() -> dict[str, Any]:
    cells = _runtime_cells()
    projection: dict[str, Any] = {
        "contract_id": "visual_final_binding_projection.v1",
        "status": "verified_support",
        "verified_slot_coverage": 1.0,
        "slot_bindings": {
            f"support:{year}": [cell["evidence_id"]]
            for year, cell in zip(VALUES, cells, strict=True)
        },
        "source_page_locators": [{"source_id": "NYSE_TM_2021", "page_label": "35"}],
    }
    metadata = {
        "evidence_selection_trace": {
            "required_slot_bindings": [
                {"slot_id": slot_id, "verification_satisfied": False}
                for slot_id in projection["slot_bindings"]
            ]
        },
        "selected_evidence": list(cells),
        "verified_evidence": list(cells),
        "verified_claim_support_evidence": list(cells),
        "cited_evidence": list(cells),
        "emitted_citation_evidence": list(cells),
        "final_binding_projection": projection,
        "slot_coverage": 1.0,
    }
    return {
        "dataset_name": "mmdocrag",
        "gold_evidence": _gold_evidence(),
        "evidence_metadata": metadata,
        "retrieved_hits": list(cells),
        "predicted_element_ids": [cell["cell_id"] for cell in cells],
    }


def test_mmdoc_locator_crosswalk_projects_exact_visual_facts_to_gold_locator():
    prediction = _prediction()

    crosswalk = apply_mmdoc_locator_crosswalk(prediction)

    assert crosswalk["contract_id"] == "mmdoc_locator_crosswalk.v1"
    assert crosswalk["status"] == "audited_exact_match"
    assert crosswalk["mappings"][0]["gold"] == {
        "source_id": "NYSE_TM_2021",
        "page": "34",
        "element_id": "image5",
        "element_type": "table",
    }
    assert set(crosswalk["mappings"][0]["runtime"]["evidence_ids"]) == {
        "cell:2017",
        "cell:2018",
        "cell:2019",
        "cell:2020",
        "cell:2021",
    }

    for item in prediction["evidence_metadata"]["verified_evidence"]:
        assert "34" in item["page_aliases"]
        assert "image5" in item["element_id_aliases"]
    assert all(
        "page_aliases" not in item
        for item in prediction["evidence_metadata"]["selected_evidence"]
    )
    assert prediction_stage_metrics(prediction)["verified_evidence_coverage"] == 1.0
    assert prediction_stage_metrics(prediction)["cited_evidence_coverage"] == 1.0
    assert prediction_stage_metrics(prediction)["verified_slot_coverage"] == 1.0
    assert prediction_stage_metric_status(prediction)["verified_slot_coverage"] == {
        "status": "measured",
        "source": "visual_final_binding_projection.v1",
    }
    assert prediction_stage_metrics(prediction)["selected_evidence_coverage"] == 1.0
    assert (
        element_locator_hit_score(
            prediction["retrieved_hits"], prediction["gold_evidence"]
        )
        == 1.0
    )


def test_mmdoc_locator_crosswalk_rejects_unanchored_page_shift():
    prediction = _prediction()
    for item in prediction["evidence_metadata"]["verified_evidence"]:
        item["row_label"] = "Unrelated table"
        item["text"] = f"Unrelated {item['period']} {item['value']}"

    crosswalk = apply_mmdoc_locator_crosswalk(prediction)

    assert crosswalk["status"] == "not_applicable"
    assert "mmdoc_locator_crosswalk" not in prediction["evidence_metadata"]


def test_mmdoc_locator_crosswalk_rejects_adjacent_page_with_different_facts():
    prediction = _prediction()
    for item in prediction["retrieved_hits"]:
        item["value"] = "999.9"
        item["text"] = f"Total shareholder return*2 {item['period']} 999.9"

    crosswalk = apply_mmdoc_locator_crosswalk(prediction)

    assert crosswalk["status"] == "not_applicable"
    assert "mmdoc_locator_crosswalk" not in prediction["evidence_metadata"]


def test_mmdoc_locator_crosswalk_rejects_unverified_projection():
    prediction = _prediction()
    projection = prediction["evidence_metadata"]["final_binding_projection"]
    projection["status"] = "retrieved_unverified"

    crosswalk = apply_mmdoc_locator_crosswalk(prediction)

    assert crosswalk["status"] == "not_applicable"
    assert prediction_stage_metrics(prediction)["verified_slot_coverage"] is None
    assert "mmdoc_locator_crosswalk" not in prediction["evidence_metadata"]


def test_mmdoc_crosswalk_exposes_audited_page_identity_without_projecting_selection():
    prediction = _prediction()
    prediction.update(
        {
            "predicted_answer": "answer",
            "gold_answers": ["answer"],
            "predicted_pages": ["35"],
            "gold_pages": [34],
        }
    )
    selected_before = [
        dict(item) for item in prediction["evidence_metadata"]["selected_evidence"]
    ]

    apply_mmdoc_locator_crosswalk(prediction)

    page_metrics = page_metric_contract(prediction)
    assert page_metrics["strict_page_hit"] == 0.0
    assert page_metrics["equivalent_page_hit"] == 1.0
    assert page_metrics["legacy_page_hit"] == 1.0
    assert prediction["evidence_metadata"]["selected_evidence"] == selected_before
    assert prediction_stage_metrics(prediction)["selected_evidence_coverage"] == 1.0
    assert (
        element_hit_score(
            prediction["predicted_element_ids"], prediction["gold_evidence"]
        )
        == 0.0
    )
    assert (
        element_locator_hit_score(
            prediction["retrieved_hits"], prediction["gold_evidence"]
        )
        == 1.0
    )


def test_mmdoc_selected_coverage_matches_audited_verified_identity_only():
    prediction = _prediction()
    selected_before = deepcopy(prediction["evidence_metadata"]["selected_evidence"])

    apply_mmdoc_locator_crosswalk(prediction)

    assert prediction_stage_metrics(prediction)["selected_evidence_coverage"] == 1.0
    assert prediction["evidence_metadata"]["selected_evidence"] == selected_before
    assert all(
        "page_aliases" not in item and "element_id_aliases" not in item
        for item in prediction["evidence_metadata"]["selected_evidence"]
    )


def test_mmdoc_selected_coverage_rejects_page_alias_without_audited_identity():
    prediction = _prediction()
    apply_mmdoc_locator_crosswalk(prediction)

    selected = prediction["evidence_metadata"]["selected_evidence"]
    for item in selected:
        item["evidence_id"] = f"unrelated:{item['period']}"
        item["canonical_id"] = f"cell:unrelated:{item['period']}"
        item["cell_id"] = f"unrelated-cell:{item['period']}"
        item["page_aliases"] = ["34"]
        item["element_id_aliases"] = ["image5"]

    assert prediction_stage_metrics(prediction)["selected_evidence_coverage"] == 0.0


def test_mmdoc_selected_coverage_requires_a_later_verified_identity():
    prediction = _prediction()
    apply_mmdoc_locator_crosswalk(prediction)
    prediction["evidence_metadata"]["verified_evidence"] = []
    prediction["evidence_metadata"]["verified_claim_support_evidence"] = []

    assert prediction_stage_metrics(prediction)["selected_evidence_coverage"] == 0.0


def test_mmdoc_finalized_stages_replay_through_exact_crosswalk_identity():
    prediction = _prediction()
    apply_mmdoc_locator_crosswalk(prediction)
    for key in (
        "verified_evidence",
        "verified_claim_support_evidence",
        "cited_evidence",
        "emitted_citation_evidence",
    ):
        for item in prediction["evidence_metadata"][key]:
            item.pop("element_id_aliases", None)

    metrics = prediction_stage_metrics(prediction)

    assert metrics["selected_evidence_coverage"] == 1.0
    assert metrics["verified_evidence_coverage"] == 1.0
    assert metrics["verified_claim_support_evidence_coverage"] == 1.0
    assert metrics["cited_evidence_coverage"] == 1.0
    assert metrics["emitted_citation_evidence_coverage"] == 1.0


def test_mmdoc_selected_projection_isolated_from_explicit_non_mmdoc_dataset():
    prediction = _prediction()
    apply_mmdoc_locator_crosswalk(prediction)
    prediction["dataset_name"] = "qasper"

    assert prediction_stage_metrics(prediction)["selected_evidence_coverage"] == 0.0


def test_mmdoc_crosswalk_does_not_infer_an_unbound_neighbour_page():
    prediction = _prediction()
    prediction.update(
        {
            "predicted_answer": "answer",
            "gold_answers": ["answer"],
            "predicted_pages": ["36"],
            "gold_pages": [34],
        }
    )

    apply_mmdoc_locator_crosswalk(prediction)

    page_metrics = page_metric_contract(prediction)
    assert page_metrics["strict_page_hit"] == 0.0
    assert page_metrics["equivalent_page_hit"] == 0.0
    assert page_metrics["legacy_page_hit"] == 0.0


def test_mmdoc_page_hit_and_coverage_keep_distinct_multi_gold_semantics():
    prediction = _prediction()
    prediction.update(
        {
            "predicted_answer": "answer",
            "gold_answers": ["answer"],
            "predicted_pages": ["35"],
            "gold_pages": [34, 36],
        }
    )
    prediction["gold_evidence"].append(
        {
            "source_id": "NYSE_TM_2021",
            "page": 36,
            "element_id": "image6",
            "element_type": "table",
            "image_quote": "Operating margin 2019 999.0",
        }
    )

    apply_mmdoc_locator_crosswalk(prediction)

    page_metrics = page_metric_contract(prediction)
    assert page_metrics["strict_page_hit"] == 0.0
    assert page_metrics["equivalent_page_hit"] == 1.0
    assert page_metrics["equivalent_evidence_page_coverage"] == 0.5
