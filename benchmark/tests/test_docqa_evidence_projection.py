from benchmark.docqa_evidence_projection import metadata_page_coverage_sources
from benchmark.schemas import BenchmarkDocument


def test_metadata_page_coverage_sources_use_explicit_file_id_for_multi_doc(tmp_path):
    first = tmp_path / "first.pdf"
    second = tmp_path / "second.pdf"
    first.write_text("first", encoding="utf-8")
    second.write_text("second", encoding="utf-8")

    sources = metadata_page_coverage_sources(
        {
            "page_coverage": [
                "9",
                {"file_id": "runtime-second", "page_label": "7"},
            ]
        },
        [
            BenchmarkDocument("doc-first", first, format_type="pdf"),
            BenchmarkDocument("doc-second", second, format_type="pdf"),
        ],
        ["runtime-first", "runtime-second"],
    )

    assert sources == ["doc-second#page:7"]
