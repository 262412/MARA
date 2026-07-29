import json

from benchmark.manifest import load_manifest


def test_load_manifest_aligns_legacy_financebench_evidence_to_parser_page(
    monkeypatch, tmp_path
):
    (tmp_path / "legacy.pdf").write_text("pdf", encoding="utf-8")
    manifest_path = tmp_path / "legacy-financebench.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "financebench_main",
                "documents": [
                    {
                        "document_id": "legacy",
                        "path": "legacy.pdf",
                        "format_type": "pdf",
                    }
                ],
                "examples": [
                    {
                        "example_id": "ex",
                        "document_ids": ["legacy"],
                        "question": "What is revenue?",
                        "answers": ["10"],
                        "evidence_sources": [
                            "{'evidence_text': 'Revenue was 10.', "
                            "'evidence_page_num': 4}"
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "benchmark.financebench_pages.extract_pdf_pages",
        lambda _path, *, page_numbers=None: [(1, "Cover"), (5, "Revenue was 10.")],
    )

    example = load_manifest(manifest_path).examples[0]

    assert example.evidence_pages == [5]
    assert example.evidence_sources == ["legacy#page:5"]
    assert example.gold_evidence == [
        {
            "document_id": "legacy",
            "page": 5,
            "dataset_page": 4,
            "citation": "legacy#page:5",
            "span": "Revenue was 10.",
            "page_alignment": "financebench_span_to_parser_page",
            "page_mapping": {
                "dataset_page": 4,
                "runtime_page": 5,
                "mapping_source": "financebench_span_to_parser_page",
                "mapping_confidence": 1.0,
                "mapping_version": "financebench_page_mapping.v1",
            },
        }
    ]


def test_load_manifest_preserves_legacy_financebench_zero_page(monkeypatch, tmp_path):
    (tmp_path / "legacy.pdf").write_text("pdf", encoding="utf-8")
    manifest_path = tmp_path / "legacy-financebench-zero-page.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "financebench_main",
                "documents": [{"document_id": "legacy", "path": "legacy.pdf"}],
                "examples": [
                    {
                        "example_id": "ex",
                        "document_ids": ["legacy"],
                        "question": "Which securities are registered?",
                        "answers": ["MMM26"],
                        "evidence_sources": [
                            "{'evidence_text': 'Title of each class MMM26', "
                            "'evidence_page_num': 0}"
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "benchmark.financebench_pages.extract_pdf_pages",
        lambda _path, *, page_numbers=None: [
            (1, "Title of each class MMM26"),
        ],
    )

    example = load_manifest(manifest_path).examples[0]

    assert example.evidence_pages == [1]
    assert example.evidence_sources == ["legacy#page:1"]
    assert example.gold_evidence[0]["dataset_page"] == 0
