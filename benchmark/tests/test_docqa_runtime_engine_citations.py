import types

from benchmark.engines import DocQARuntimeEngine
from benchmark.schemas import BenchmarkConfig, BenchmarkDocument


def test_docqa_runtime_engine_separates_emitted_citations_from_evidence_sources(
    tmp_path,
):
    doc_path = tmp_path / "doc.txt"
    doc_path.write_text("runtime text", encoding="utf-8")
    engine = DocQARuntimeEngine(
        BenchmarkConfig(suite_name="runtime", output_dir=tmp_path / "out")
    )
    response = types.SimpleNamespace(
        answer="Runtime answer [doc#page:2].",
        references_text="Extra reference file-1#page:5",
        evidence_metadata={},
        evidence_bundle={
            "route": "doc_text",
            "items": [
                {
                    "evidence_id": "hit-1",
                    "source_id": "file-1",
                    "source_name": "doc.txt",
                    "page_label": "2",
                    "modality": "text",
                    "text": "Primary evidence.",
                    "source_backrefs": ["file-1#page:2"],
                },
                {
                    "evidence_id": "hit-2",
                    "source_id": "file-1",
                    "source_name": "doc.txt",
                    "page_label": "99",
                    "modality": "text",
                    "text": "Extra retrieved evidence.",
                    "source_backrefs": ["file-1#page:99"],
                },
            ],
        },
    )

    _, _, predicted_sources, predicted_citations, _ = engine._response_evidence_outputs(
        response=response,
        documents=[
            BenchmarkDocument(document_id="doc", path=doc_path, format_type="txt")
        ],
        selected_file_ids=["file-1"],
    )

    assert predicted_sources == ["doc#page:2", "doc#page:99", "doc#page:5"]
    assert predicted_citations == ["doc#page:2"]


def test_docqa_runtime_engine_maps_indexed_inline_citations_to_evidence_sources(
    tmp_path,
):
    doc_path = tmp_path / "doc.txt"
    doc_path.write_text("runtime text", encoding="utf-8")
    engine = DocQARuntimeEngine(
        BenchmarkConfig(suite_name="runtime", output_dir=tmp_path / "out")
    )
    response = types.SimpleNamespace(
        answer="Waxahachie, Texas [1]. Other support [2, 3].",
        references_text="",
        evidence_metadata={},
        evidence_bundle={
            "route": "doc_text",
            "items": [
                {
                    "evidence_id": "hit-1",
                    "source_id": "file-1",
                    "source_name": "doc.txt",
                    "text": "Waxahachie is a city in Texas.",
                    "source_backrefs": ["file-1#source"],
                },
                {
                    "evidence_id": "hit-2",
                    "source_id": "file-1",
                    "source_name": "doc.txt",
                    "page_label": "5",
                    "text": "The event was held there.",
                    "source_backrefs": ["file-1#page:5"],
                },
                {
                    "evidence_id": "hit-3",
                    "source_id": "file-1",
                    "source_name": "doc.txt",
                    "page_label": "9",
                    "text": "The date appears later in the source.",
                    "source_backrefs": ["file-1#page:9"],
                },
            ],
        },
    )

    (
        _,
        _,
        _predicted_sources,
        predicted_citations,
        _,
    ) = engine._response_evidence_outputs(
        response=response,
        documents=[
            BenchmarkDocument(document_id="doc", path=doc_path, format_type="txt")
        ],
        selected_file_ids=["file-1"],
    )

    assert predicted_citations == ["doc#source", "doc#page:5", "doc#page:9"]
