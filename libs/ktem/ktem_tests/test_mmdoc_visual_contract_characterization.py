from __future__ import annotations

import pytest
from ktem.docqa._runtime_models import DocQARequest
from ktem.docqa.controller import RetrieveDecision
from ktem.docqa.evidence import build_evidence_bundle
from ktem.docqa.query_planning import ensure_request_query_plan
from ktem.docqa.verification import verify_decision
from ktem.docqa.visual_evidence_authority import record_visual_answer_authority
from ktem.reasoning.mara_route_scorer import score_adaptive_route

QUESTION = "How did the Total Shareholder Return change over the fiscal years from 2017 to 2021?"
VALUES = {
    "2017": "1082.4",
    "2018": "1200.0",
    "2019": "1186.7",
    "2020": "810.8",
    "2021": "921.0",
}


def _page_item() -> dict[str, object]:
    return {
        "evidence_id": "page-image:report:34",
        "file_id": "report",
        "file_name": "P18-1125.pdf",
        "page_label": "34",
        "modality": "page_image",
        "text": "Total Shareholder Return fiscal-year table.",
        "ocr_text": "Total Shareholder Return fiscal-year table.",
        "source_backrefs": ["report#page:34"],
        "metadata": {
            "visual_extractions": [
                {
                    "table_id": "shareholder-return",
                    "cell_id": f"shareholder-return:{year}",
                    "row_label": "Total Shareholder Return",
                    "column_label": year,
                    "period": year,
                    "value": value,
                    "cell_role": "data",
                    "modality": "table",
                    "text": f"Total Shareholder Return {year} {value}",
                    "extraction_source": "ocr_table",
                }
                for year, value in VALUES.items()
            ]
        },
    }


def _request(route: str) -> DocQARequest:
    request = DocQARequest(
        prompt=QUESTION,
        retrieval_query=QUESTION,
        task_type="numeric",
        answer_type="numeric",
        verification_mode="strict",
        verification_domain="mmdocrag",
        origin="benchmark",
        route_policy=route,
        allowed_routes=["doc_text", "doc_page_image", "doc_element", "hybrid"],
        selected_file_ids=["report"],
    )
    ensure_request_query_plan(request)
    return request


@pytest.mark.parametrize(
    "route", ["doc_text", "doc_page_image", "doc_element", "hybrid"]
)
def test_mmdoc_four_routes_project_page_extractions_to_typed_operands(route: str):
    page = _page_item()
    metadata = {
        "evidence": [page],
        "page_image_index": [page],
        "elements": [page],
    }

    bundle = build_evidence_bundle(route, _request(route), metadata)

    projection = bundle.metadata["visual_typed_projection"]
    assert projection["projected_count"] == 5
    slots = {
        slot["slot_id"]: slot
        for slot in bundle.metadata["query_plan"]["evidence_slots"]
    }
    assert set(slots) == {f"operand:{year}" for year in VALUES}
    assert all(slot["status"] == "filled" for slot in slots.values())
    assert all(slot["evidence_ids"] for slot in slots.values())
    bound_values = {
        item["value"] for item in bundle.items if item.get("value") in VALUES.values()
    }
    assert bound_values == set(VALUES.values())


def test_mmdoc_visual_verification_does_not_commit_filled_typed_slots():
    request = _request("doc_page_image")
    page = _page_item()
    bundle = build_evidence_bundle(
        "doc_page_image",
        request,
        {"page_image_index": [page], "evidence": [page]},
    )
    answer = "The return changed from 1082.4 in 2017 to 921.0 in 2021."
    assert record_visual_answer_authority(bundle, answer, backend="test_ocr")

    decision = verify_decision(
        request,
        RetrieveDecision("good", "typed visual evidence is complete"),
        bundle,
        answer,
    )

    assert decision.status == "unsupported"
    assert decision.typed_authority == {}
    assert decision.verified_support_slot_ids == []
    assert all(
        slot.status == "filled"
        for slot in request.query_plan.evidence_slots
        if slot.required_for_execution
    )


def test_mmdoc_controller_does_not_cost_gate_away_required_visual_typed_route():
    payload = score_adaptive_route(
        {
            "task_type": "qa",
            "modalities": ["text"],
            "available_modalities": ["text", "page_image"],
        },
        question=QUESTION,
        allowed_routes=["doc_text", "doc_page_image", "hybrid"],
        planner_route="doc_text",
        planner_reason="text route would be cheaper",
        dataset_family="mmdocrag",
        route_probe={
            "text": {
                "evidence_count": 5,
                "top_score": 0.95,
                "top_margin": 0.2,
                "locator_quality": 1.0,
                "has_text_or_ocr": True,
                "backend_healthy": True,
            },
            "visual": {
                "evidence_count": 1,
                "top_score": 0.92,
                "top_margin": 0.3,
                "locator_quality": 1.0,
                "has_text_or_ocr": True,
                "backend_healthy": True,
            },
            "element": {},
            "graph": {},
        },
        latency_budget={"vlm_generator_available": True},
    )

    assert payload["routing_features"]["requires_typed_visual_evidence"] is True
    assert payload["route"] == "doc_page_image"
    assert payload["cost_gate_decision"] == "required_evidence_preserved"
