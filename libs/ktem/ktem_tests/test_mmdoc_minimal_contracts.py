from __future__ import annotations

from types import SimpleNamespace

from ktem.docqa.query_planning import build_query_plan
from ktem.docqa.visual_evidence_authority import (
    project_visual_evidence_to_typed_items,
    typed_visual_evidence_path,
)
from ktem.reasoning.mara_route_retrieval import (
    _bridge_element_records_to_page_records,
    _page_image_records_for_pipeline,
)

from benchmark import docqa_image_documents, ocr_layout_sidecars
from benchmark.schemas import BenchmarkDocument

QUESTION = (
    "How did the Total Shareholder Return change over the fiscal years "
    "from 2017 to 2021?"
)


def test_descriptive_multi_period_trend_creates_typed_visual_support_slots():
    plan = build_query_plan(
        QUESTION,
        answer_type="descriptive",
        verification_domain="mmdocrag",
    )

    assert plan.answer_type == "free_text"
    assert plan.question_type == "visual_time_series"
    assert [slot.slot_id for slot in plan.evidence_slots] == [
        "support:2017",
        "support:2018",
        "support:2019",
        "support:2020",
        "support:2021",
    ]
    assert not any(slot.required_for_execution for slot in plan.evidence_slots)
    assert all(slot.required_for_verification for slot in plan.evidence_slots)
    assert all(
        slot.statement_kind == "visual_time_series_cell" for slot in plan.evidence_slots
    )
    assert plan.constraints["requires_structure"] is True


def test_plain_mmdoc_prose_question_does_not_create_time_series_slots():
    plan = build_query_plan(
        "Explain the company's shareholder engagement policy.",
        answer_type="descriptive",
        verification_domain="mmdocrag",
    )

    assert plan.answer_type == "free_text"
    assert plan.question_type == "long_form"
    assert plan.evidence_slots == ()


def test_numeric_multi_period_answer_type_keeps_operand_contract():
    plan = build_query_plan(
        QUESTION,
        answer_type="numeric",
        verification_domain="mmdocrag",
    )

    assert plan.answer_type == "numeric"
    assert plan.question_type == "multi_period_numeric"
    assert [slot.slot_id for slot in plan.evidence_slots] == [
        "operand:2017",
        "operand:2018",
        "operand:2019",
        "operand:2020",
        "operand:2021",
    ]


def _typed_authority_bundle(
    status: str,
    *,
    include_typed_item: bool = True,
) -> SimpleNamespace:
    page = {
        "evidence_id": "page-image:report:34",
        "file_id": "report",
        "page_label": "34",
        "modality": "page_image",
        "evidence_level": "page",
        "text": "Total Shareholder Return 2017 1082.4",
    }
    typed = {
        "file_id": "report",
        "page_label": "34",
        "element_id": "return-table",
        "cell_id": "return:2017",
        "evidence_level": "cell",
        "modality": "table",
        "text": "Total Shareholder Return 2017 1082.4",
        "value": "1082.4",
        "period": "2017",
    }
    evidence_id = "cell:report:return%3A2017"
    typed["evidence_id"] = evidence_id
    plan = {
        "state_version": 4,
        "evidence_slots": [
            {
                "slot_id": "operand:2017",
                "role": "operand",
                "required_for_execution": True,
                "required_for_verification": True,
                "status": status,
                "evidence_ids": [evidence_id],
            }
        ],
    }
    items = [page]
    if include_typed_item:
        items.append(typed)
    return SimpleNamespace(items=items, metadata={"query_plan": plan})


def test_filled_visual_slot_is_not_advertised_as_verified():
    assert typed_visual_evidence_path(_typed_authority_bundle("filled")) is None


def test_retrieved_unverified_visual_slot_is_not_advertised_as_verified():
    assert (
        typed_visual_evidence_path(_typed_authority_bundle("retrieved_unverified"))
        is None
    )


def test_verified_visual_slot_requires_selected_typed_evidence():
    path = typed_visual_evidence_path(_typed_authority_bundle("verified_support"))
    assert path is not None
    assert path["verified_support_slot_ids"] == ["operand:2017"]

    assert (
        typed_visual_evidence_path(
            _typed_authority_bundle("verified_support", include_typed_item=False)
        )
        is None
    )


class _FakePage:
    def __init__(self, blocks):
        self.blocks = blocks

    def get_text(self, mode, sort=False):
        assert mode == "blocks"
        assert sort is True
        return self.blocks


class _FakeDocument:
    def __init__(self, pages):
        self.pages = pages

    def __len__(self):
        return len(self.pages)

    def load_page(self, index):
        return self.pages[index]

    def close(self):
        pass


class _FakeFitz:
    def __init__(self, document):
        self.document = document

    def open(self, _path):
        return self.document


def _vertical_fixture_fitz() -> _FakeFitz:
    return _FakeFitz(
        _FakeDocument(
            [
                _FakePage(
                    [
                        (0, 0, 100, 30, "2017/3\n2018/3\n2019/3\n2020/3\n2021/3"),
                        (
                            10,
                            40,
                            110,
                            80,
                            "Dividend per share\n(yen)\n30\n35\n40\n45\n50",
                        ),
                        (
                            10,
                            90,
                            110,
                            140,
                            "Total shareholder return*2\n"
                            "(billions of yen)\n1,082.4\n1,200.0\n"
                            "1,186.7\n810.8\n921.0",
                        ),
                    ]
                )
            ]
        )
    )


def _runtime_page_records(*_args, **_kwargs):
    return [
        {
            "evidence_id": "page-image:runtime-source:1",
            "file_id": "runtime-source",
            "page_label": "1",
            "modality": "page_image",
            "evidence_level": "page",
            "text": "Total Shareholder Return 2017 1082.4 2018 1200.0",
            "ocr_text": "Total Shareholder Return 2017 1082.4 2018 1200.0",
            "metadata": {},
        }
    ]


def _runtime_pipeline(pdf_path, element_records):
    return SimpleNamespace(
        selected_file_records=[
            {
                "file_id": "runtime-source",
                "file_name": "source.pdf",
                "path": str(pdf_path),
            }
        ],
        element_index_records=element_records,
        docqa_request=SimpleNamespace(
            source_identity_crosswalk=[
                {
                    "canonical_dataset_id": "source",
                    "runtime_file_id": "runtime-source",
                    "runtime_source_id": "runtime-source",
                    "document_path": str(pdf_path),
                    "filename": "source.pdf",
                    "aliases": ["source"],
                }
            ]
        ),
    )


def test_pdf_ocr_cells_bridge_to_page_parent_and_project_without_gold(
    monkeypatch,
    tmp_path,
):
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF")
    monkeypatch.setattr(
        ocr_layout_sidecars,
        "_import_fitz",
        _vertical_fixture_fitz,
    )
    document = BenchmarkDocument(
        document_id="source",
        path=pdf_path,
        format_type="pdf",
        metadata={},
    )
    element_records = docqa_image_documents.mmdoc_element_index_records_from_documents(
        [document]
    )
    assert element_records
    row_extractions = [
        extraction
        for record in element_records
        for extraction in record["metadata"].get("visual_extractions", [])
    ]
    tsr_extractions = [
        extraction
        for extraction in row_extractions
        if extraction.get("row_label") == "Total shareholder return*2"
    ]
    assert len(tsr_extractions) == 5
    assert {item["period"] for item in tsr_extractions} == {
        "2017",
        "2018",
        "2019",
        "2020",
        "2021",
    }
    assert {item["value"] for item in tsr_extractions} == {
        "1082.4",
        "1200.0",
        "1186.7",
        "810.8",
        "921.0",
    }
    assert all(item["unit"] == "billions of yen" for item in tsr_extractions)

    monkeypatch.setattr(
        "ktem.reasoning.mara_route_retrieval.build_local_page_image_records",
        _runtime_page_records,
    )
    pipeline = _runtime_pipeline(pdf_path, element_records)

    page_records = _page_image_records_for_pipeline(pipeline)
    extractions = page_records[0]["metadata"]["visual_extractions"]
    assert len(extractions) == 10

    projected, trace = project_visual_evidence_to_typed_items(page_records)
    assert trace["projected_count"] == 10
    assert {
        item["value"]
        for item in projected
        if item.get("evidence_level") == "cell"
        and item.get("row_label") == "Total shareholder return*2"
    } == {
        "1082.4",
        "1200.0",
        "1186.7",
        "810.8",
        "921.0",
    }


def test_plain_text_element_does_not_bridge_as_visual_extraction():
    page = {
        "evidence_id": "page-image:source:1",
        "file_id": "source",
        "page_label": "1",
        "modality": "page_image",
        "evidence_level": "page",
        "metadata": {},
    }
    plain_text_element = {
        "file_id": "source",
        "page_label": "1",
        "element_id": "text-1",
        "element_type": "text",
        "text": "Total shareholder return 2017 1082.4",
        "metadata": {},
    }

    bridged = _bridge_element_records_to_page_records([page], [plain_text_element])

    assert "visual_extractions" not in bridged[0].get("metadata", {})
    projected, trace = project_visual_evidence_to_typed_items(bridged)
    assert trace["projected_count"] == 0
    assert all(item.get("evidence_level") != "cell" for item in projected)


def test_ambiguous_source_alias_does_not_bridge_visual_extraction():
    page = {
        "evidence_id": "page-image:report.pdf:1",
        "file_name": "report.pdf",
        "page_label": "1",
        "modality": "page_image",
        "evidence_level": "page",
        "metadata": {},
    }
    element = {
        "file_name": "report.pdf",
        "page_label": "1",
        "element_id": "table-1",
        "metadata": {
            "visual_extractions": [
                {
                    "cell_id": "table-1:cell:1:1",
                    "value": "1082.4",
                    "period": "2017",
                    "modality": "table",
                    "evidence_level": "cell",
                }
            ]
        },
    }
    crosswalk = [
        {
            "canonical_dataset_id": "report-a",
            "runtime_file_id": "runtime-a",
            "filename": "report.pdf",
        },
        {
            "canonical_dataset_id": "report-b",
            "runtime_file_id": "runtime-b",
            "filename": "report.pdf",
        },
    ]

    bridged = _bridge_element_records_to_page_records(
        [page], [element], crosswalk=crosswalk
    )

    assert "visual_extractions" not in bridged[0].get("metadata", {})


def test_pdf_ocr_element_cache_invalidates_when_file_identity_changes(
    monkeypatch,
    request,
    tmp_path,
):
    cache = docqa_image_documents._cached_pdf_ocr_layout_elements
    cache.cache_clear()
    request.addfinalizer(cache.cache_clear)
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF-1")
    calls = []

    def fake_producer(path, *, document_id):
        calls.append((str(path), document_id))
        return {
            "layout_elements": [
                {
                    "page_label": "1",
                    "element_id": f"element-{len(calls)}",
                    "text": "source text",
                }
            ]
        }

    monkeypatch.setattr(
        docqa_image_documents,
        "build_pdf_ocr_layout_sidecar",
        fake_producer,
    )
    document = BenchmarkDocument(
        document_id="source",
        path=pdf_path,
        format_type="pdf",
        metadata={},
    )

    first = docqa_image_documents.mmdoc_element_index_records_from_documents([document])
    second = docqa_image_documents.mmdoc_element_index_records_from_documents(
        [document]
    )
    assert len(first) == len(second) == 1
    assert len(calls) == 1

    pdf_path.write_bytes(b"%PDF-1 changed")
    third = docqa_image_documents.mmdoc_element_index_records_from_documents([document])

    assert len(third) == 1
    assert len(calls) == 2


def test_pdf_ocr_layout_producer_is_opt_in(monkeypatch, tmp_path):
    pdf_path = tmp_path / "source.pdf"
    pdf_path.write_bytes(b"%PDF")
    calls = []

    def fake_producer(path, *, document_id):
        calls.append((str(path), document_id))
        return {"layout_elements": []}

    monkeypatch.setattr(
        docqa_image_documents,
        "build_pdf_ocr_layout_sidecar",
        fake_producer,
    )
    document = BenchmarkDocument(
        document_id="source",
        path=pdf_path,
        format_type="pdf",
        metadata={},
    )

    assert docqa_image_documents.element_index_records_from_documents([document]) == []
    assert calls == []


def test_page_only_ocr_does_not_project_atomic_visual_cells():
    page = {
        "evidence_id": "page-image:source:1",
        "file_id": "source",
        "page_label": "1",
        "modality": "page_image",
        "evidence_level": "page",
        "text": "Metric 2017 2018 Total Shareholder Return 1082.4 1200.0",
        "ocr_text": "Metric 2017 2018 Total Shareholder Return 1082.4 1200.0",
        "metadata": {},
    }

    projected, trace = project_visual_evidence_to_typed_items([page])

    assert trace["projected_count"] == 0
    assert all(item.get("evidence_level") != "cell" for item in projected)
