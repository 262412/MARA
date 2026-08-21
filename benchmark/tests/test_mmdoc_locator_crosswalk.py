from __future__ import annotations

from typing import Any

from benchmark.element_locator_metrics import element_locator_hit_score
from benchmark.mmdoc_locator_crosswalk import apply_mmdoc_locator_crosswalk
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
    assert prediction_stage_metrics(prediction)["selected_evidence_coverage"] == 0.0
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
