import json

from benchmark.manifest import load_manifest
from benchmark.normalizers import normalize_financebench_manifest


def test_normalize_financebench_manifest_aligns_gold_span_to_parser_page(
    monkeypatch, tmp_path
):
    data_dir = tmp_path / "data"
    pdf_dir = tmp_path / "pdfs"
    data_dir.mkdir()
    pdf_dir.mkdir()
    pdf_path = pdf_dir / "company_a.pdf"
    pdf_path.write_text("pdf", encoding="utf-8")
    (data_dir / "financebench_open_source.jsonl").write_text(
        json.dumps(
            {
                "financebench_id": "financebench_id_1",
                "doc_name": "company_a.pdf",
                "question": "What is revenue?",
                "answer": "10",
                "evidence": [
                    {
                        "evidence_text": "Revenue was 10.",
                        "evidence_page_num": 4,
                    }
                ],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "benchmark.financebench_pages.extract_pdf_pages",
        lambda _path, *, page_numbers=None: [(1, "Cover"), (5, "Revenue was 10.")],
    )

    manifest_path = tmp_path / "financebench.json"
    normalize_financebench_manifest(tmp_path, manifest_path)
    example = load_manifest(manifest_path).examples[0]

    assert example.evidence_pages == [5]
    assert example.evidence_sources == ["company_a#page:5"]
    assert example.gold_evidence == [
        {
            "document_id": "company_a",
            "page": 5,
            "dataset_page": 4,
            "citation": "company_a#page:5",
            "span": "Revenue was 10.",
            "page_alignment": "financebench_span_to_parser_page",
        }
    ]


def test_normalize_financebench_marks_metrics_generated_examples_numeric(tmp_path):
    data_dir = tmp_path / "data"
    pdf_dir = tmp_path / "pdfs"
    data_dir.mkdir()
    pdf_dir.mkdir()
    (pdf_dir / "company_a.pdf").write_text("pdf", encoding="utf-8")
    (data_dir / "financebench_open_source.jsonl").write_text(
        json.dumps(
            {
                "financebench_id": "financebench_numeric",
                "doc_name": "company_a.pdf",
                "question": "What was FY2021 capital expenditure?",
                "answer": "$4.625 billion",
                "question_type": "metrics-generated",
                "question_reasoning": "Information extraction",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    manifest_path = tmp_path / "financebench.json"
    normalize_financebench_manifest(tmp_path, manifest_path)
    example = load_manifest(manifest_path).examples[0]

    assert example.answer_type == "numeric"
    assert example.metadata["dataset_family"] == "financebench"
