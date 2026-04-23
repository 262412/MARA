import json

from benchmark.manifest import load_manifest
from benchmark.normalizers import (
    normalize_financebench_manifest,
    normalize_format_robustness_manifest,
)


def test_normalize_format_robustness_manifest(tmp_path):
    pdf_dir = tmp_path / "pdf"
    pdf_dir.mkdir(parents=True)
    (pdf_dir / "1_sample.pdf").write_text("dummy", encoding="utf-8")
    (pdf_dir / "1_metadata.json").write_text(
        json.dumps(
            {
                "questions": [
                    {"question": "What is this?", "answer": "sample"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    manifest_path = tmp_path / "format.json"
    normalize_format_robustness_manifest(tmp_path, manifest_path)
    bundle = load_manifest(manifest_path)

    assert bundle.dataset_name == "format_robustness"
    assert len(bundle.documents) == 1
    assert len(bundle.examples) == 1
    assert bundle.examples[0].answers == ["sample"]


def test_normalize_financebench_manifest(tmp_path):
    data_dir = tmp_path / "data"
    pdf_dir = tmp_path / "pdfs"
    data_dir.mkdir()
    pdf_dir.mkdir()
    (pdf_dir / "company_a.pdf").write_text("pdf", encoding="utf-8")
    (data_dir / "financebench_open_source.jsonl").write_text(
        json.dumps(
            {
                "id": "1",
                "doc_name": "company_a.pdf",
                "question": "What is revenue?",
                "answer": "10",
                "evidence_strings": ["Revenue was 10."],
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    manifest_path = tmp_path / "financebench.json"
    normalize_financebench_manifest(tmp_path, manifest_path)
    bundle = load_manifest(manifest_path)

    assert bundle.dataset_name == "financebench"
    assert len(bundle.examples) == 1
    assert bundle.examples[0].evidence_sources == ["Revenue was 10."]


def test_load_v2_manifest_supports_documents_scope_modality_answer_type_and_evidence(tmp_path):
    (tmp_path / "doc-a.pdf").write_text("a", encoding="utf-8")
    (tmp_path / "doc-b.xlsx").write_text("b", encoding="utf-8")
    manifest_path = tmp_path / "v2.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "v2_suite",
                "documents": [
                    {
                        "document_id": "doc-a",
                        "path": "doc-a.pdf",
                        "format_type": "pdf",
                        "modality": "text",
                    },
                    {
                        "document_id": "doc-b",
                        "path": "doc-b.xlsx",
                        "format_type": "xlsx",
                        "modality": "table",
                    },
                ],
                "examples": [
                    {
                        "example_id": "ex-1",
                        "document_ids": ["doc-a", "doc-b"],
                        "scope": "multi_document",
                        "modality": "table",
                        "answer_type": "numeric",
                        "question": "What is the combined revenue?",
                        "answers": ["42"],
                        "gold_evidence": [
                            {
                                "document_id": "doc-a",
                                "page": 2,
                                "element_id": "table-1",
                                "span": "Revenue was 20",
                                "citation": "doc-a#page:2",
                            },
                            {
                                "document_id": "doc-b",
                                "element_id": "cell-b2",
                                "span": "Revenue was 22",
                            },
                        ],
                    }
                ],
                "routes": [
                    {"engine": "text-rag", "scope": "multi_document", "route": "hybrid"}
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    bundle = load_manifest(manifest_path)

    assert bundle.schema_version == 2
    assert bundle.dataset_name == "v2_suite"
    assert bundle.documents["doc-b"].modality == "table"
    assert bundle.routes == [
        {
            "route_id": "hybrid",
            "route_name": "hybrid",
            "engine": "text-rag",
            "scope": "multi_document",
            "reader_mode": "default",
            "retrieval_mode": "hybrid",
            "top_k": 5,
            "use_generation": True,
            "cost_profile": None,
        }
    ]
    example = bundle.examples[0]
    assert example.document_ids == ["doc-a", "doc-b"]
    assert example.scope == "multi_document"
    assert example.modality == "table"
    assert example.answer_type == "numeric"
    assert example.gold_evidence[0]["element_id"] == "table-1"


def test_load_v2_manifest_normalizes_route_matrix_defaults_and_aliases(tmp_path):
    (tmp_path / "doc.pdf").write_text("pdf", encoding="utf-8")
    manifest_path = tmp_path / "v2-routes.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "route_suite",
                "documents": [
                    {
                        "document_id": "doc",
                        "path": "doc.pdf",
                    }
                ],
                "examples": [
                    {
                        "document_id": "doc",
                        "question": "What is it?",
                        "answer": "pdf",
                    }
                ],
                "route_matrix": [
                    {
                        "id": "docqa-hybrid",
                        "name": "DocQA hybrid",
                        "engine": "docqa_runtime",
                        "scope": "multi-document",
                        "reader_mode": "docling",
                        "retrieval_mode": "hybrid",
                        "top_k": 8,
                        "use_generation": False,
                        "cost_profile": "quality",
                    },
                    {
                        "route": "legacy",
                        "engine": "kotaemon-text-rag",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    bundle = load_manifest(manifest_path)

    assert bundle.routes == [
        {
            "route_id": "docqa-hybrid",
            "route_name": "DocQA hybrid",
            "engine": "docqa_runtime",
            "scope": "multi_document",
            "reader_mode": "docling",
            "retrieval_mode": "hybrid",
            "top_k": 8,
            "use_generation": False,
            "cost_profile": "quality",
        },
        {
            "route_id": "legacy",
            "route_name": "legacy",
            "engine": "legacy_text_rag",
            "scope": "document",
            "reader_mode": "default",
            "retrieval_mode": "hybrid",
            "top_k": 5,
            "use_generation": True,
            "cost_profile": None,
        },
    ]


def test_load_v1_manifest_sets_v2_defaults(tmp_path):
    (tmp_path / "doc.pdf").write_text("pdf", encoding="utf-8")
    manifest_path = tmp_path / "v1.json"
    manifest_path.write_text(
        json.dumps(
            {
                "dataset_name": "v1_suite",
                "examples": [
                    {
                        "document_id": "doc",
                        "document_path": "doc.pdf",
                        "question": "What is it?",
                        "answer": "pdf",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    bundle = load_manifest(manifest_path)
    example = bundle.examples[0]

    assert bundle.schema_version == 1
    assert example.scope == "document"
    assert example.modality == "text"
    assert example.answer_type == "extractive"
    assert example.document_ids == ["doc"]


def test_load_manifest_accepts_utf8_bom(tmp_path):
    (tmp_path / "doc.txt").write_text("alpha", encoding="utf-8")
    manifest_path = tmp_path / "bom.json"
    manifest_path.write_text(
        '\ufeff{"dataset_name": "bom", "examples": ['
        '{"document_id": "doc", "document_path": "doc.txt", '
        '"question": "What?", "answer": "alpha"}]}',
        encoding="utf-8",
    )

    bundle = load_manifest(manifest_path)

    assert bundle.dataset_name == "bom"
    assert bundle.examples[0].answers == ["alpha"]
