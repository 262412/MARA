import types

from benchmark.engines import DocQARuntimeEngine
from benchmark.schemas import BenchmarkConfig, BenchmarkDocument


def test_docqa_runtime_evidence_output_preserves_citation_fields_as_source_backrefs(
    tmp_path,
):
    doc_path = tmp_path / "doc.txt"
    doc_path.write_text("runtime text", encoding="utf-8")
    engine = DocQARuntimeEngine(
        BenchmarkConfig(suite_name="runtime", output_dir=tmp_path / "out")
    )
    response = types.SimpleNamespace(
        answer="Revenue increased [1].",
        references_text="",
        evidence_bundle={"route": "doc_text", "items": []},
        evidence_metadata={
            "evidence": [
                {
                    "evidence_id": "metadata-hit",
                    "file_id": "file-1",
                    "file_name": "doc.txt",
                    "page_label": "4",
                    "citation": "file-1#section:results",
                    "text": "Revenue increased.",
                }
            ]
        },
    )

    (
        _,
        retrieved_hits,
        predicted_sources,
        predicted_citations,
        _,
    ) = engine._response_evidence_outputs(
        response=response,
        documents=[
            BenchmarkDocument(document_id="doc", path=doc_path, format_type="txt")
        ],
        selected_file_ids=["file-1"],
    )

    assert retrieved_hits[0]["source_backrefs"] == ["doc#section:results"]
    assert predicted_sources == ["doc#section:results"]
    assert predicted_citations == ["doc#section:results"]
