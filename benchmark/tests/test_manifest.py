import json

from benchmark.manifest import DEFAULT_MARA_ROUTES, load_manifest
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


def test_load_v2_manifest_supports_documents_scope_modality_answer_type_and_evidence(
    tmp_path,
):
    (tmp_path / "doc-a.pdf").write_text("a", encoding="utf-8")
    (tmp_path / "doc-b.xlsx").write_text("b", encoding="utf-8")
    manifest_path = tmp_path / "v2.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "v2_suite",
                "documents": [
                    {"document_id": "doc-a", "path": "doc-a.pdf", "format_type": "pdf"},
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
                        "expected_formats": ["markdown_table", "latex"],
                        "expected_guardrails": {
                            "allow_abstention": False,
                            "rewrite_skipped": True,
                        },
                        "gold_evidence": [
                            {
                                "document_id": "doc-a",
                                "page": 2,
                                "element_id": "table-1",
                                "span": "Revenue was 20",
                                "citation": "doc-a#page:2",
                            },
                            {"document_id": "doc-b", "element_id": "cell-b2"},
                        ],
                    }
                ],
                "routes": [
                    {
                        "engine": "text-rag",
                        "scope": "multi_document",
                        "route": "hybrid",
                        "reasoning": "mara",
                        "agent_mode": "fast",
                        "task_type": "qa",
                        "artifact_type": "study_guide",
                    }
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
    route = bundle.routes[0]
    assert route["route_id"] == "hybrid"
    assert route["engine"] == "text-rag"
    assert route["scope"] == "multi_document"
    assert route["reasoning_type"] == "mara"
    assert route["agent_mode"] == "fast"
    assert route["task_type"] == "qa"
    assert route["artifact_type"] == "study_guide"
    example = bundle.examples[0]
    assert example.document_ids == ["doc-a", "doc-b"]
    assert example.scope == "multi_document"
    assert example.modality == "table"
    assert example.answer_type == "numeric"
    assert example.expected_formats == ["markdown_table", "latex"]
    assert example.expected_guardrails == {
        "allow_abstention": False,
        "rewrite_skipped": True,
    }
    assert example.gold_evidence[0]["element_id"] == "table-1"


def test_load_v2_manifest_normalizes_route_matrix_defaults_and_aliases(tmp_path):
    (tmp_path / "doc.pdf").write_text("pdf", encoding="utf-8")
    manifest_path = tmp_path / "v2-routes.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "route_suite",
                "documents": [{"document_id": "doc", "path": "doc.pdf"}],
                "examples": [
                    {"document_id": "doc", "question": "What is it?", "answer": "pdf"}
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
                        "reasoning_type": "mara",
                        "agent_mode": "thorough",
                        "task_type": "summary",
                        "artifact_type": "slide_outline",
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
            "reasoning_type": "mara",
            "agent_mode": "thorough",
            "task_type": "summary",
            "artifact_type": "slide_outline",
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
            "reasoning_type": None,
            "agent_mode": None,
            "task_type": None,
            "artifact_type": None,
        },
    ]


def test_load_v2_manifest_preserves_controller_route_fields(tmp_path):
    (tmp_path / "doc.pdf").write_text("pdf", encoding="utf-8")
    manifest_path = tmp_path / "v2-controller-routes.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "documents": [{"document_id": "doc", "path": "doc.pdf"}],
                "examples": [
                    {"document_id": "doc", "question": "What is it?", "answer": "pdf"}
                ],
                "routes": [
                    {
                        "route_id": "controller_llm",
                        "engine": "docqa_runtime",
                        "controller_mode": "llm",
                        "route_policy": "hybrid",
                        "verification_mode": "strict",
                        "backend_status": "not_configured",
                        "requires_backend_config": True,
                        "missing_backends": ["visual_generator"],
                        "implementation_stage": "prototype_visual_route",
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    bundle = load_manifest(manifest_path)

    assert bundle.routes[0]["controller_mode"] == "llm"
    assert bundle.routes[0]["route_policy"] == "hybrid"
    assert bundle.routes[0]["verification_mode"] == "strict"
    assert bundle.routes[0]["backend_status"] == "not_configured"
    assert bundle.routes[0]["requires_backend_config"] is True
    assert bundle.routes[0]["missing_backends"] == ["visual_generator"]
    assert bundle.routes[0]["implementation_stage"] == "prototype_visual_route"


def test_load_v2_manifest_preserves_planner_model_and_allowed_routes(tmp_path):
    (tmp_path / "doc.pdf").write_text("pdf", encoding="utf-8")
    manifest_path = tmp_path / "v2-planner-routes.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "documents": [{"document_id": "doc", "path": "doc.pdf"}],
                "examples": [
                    {"document_id": "doc", "question": "What is it?", "answer": "pdf"}
                ],
                "routes": [
                    {
                        "route_id": "controller_llm",
                        "engine": "docqa_runtime",
                        "planner_model": "gpt-4o-mini",
                        "allowed_routes": ["doc_text", "graph_global"],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    route = load_manifest(manifest_path).routes[0]

    assert route["planner_model"] == "gpt-4o-mini"
    assert route["allowed_routes"] == ["doc_text", "graph_global"]


def test_default_mara_routes_cover_full_route_ablation_matrix():
    route_ids = [route["route_id"] for route in DEFAULT_MARA_ROUTES]

    assert route_ids == [
        "direct_answer",
        "text_rag",
        "page_image_rag_smoke",
        "page_image_rag_vlm",
        "element_rag",
        "graph_rag_local",
        "graph_rag_global",
        "hybrid_rag",
        "controller_auto",
        "crag_guarded",
    ]
    assert DEFAULT_MARA_ROUTES[0]["route_policy"] == "direct"
    assert DEFAULT_MARA_ROUTES[2]["allowed_routes"] == ["doc_page_image"]
    assert DEFAULT_MARA_ROUTES[3]["visual_retriever_backend"] == (
        "local_late_interaction"
    )
    assert DEFAULT_MARA_ROUTES[3]["generator_backend"] == "evidence_only_without_vlm"
    assert DEFAULT_MARA_ROUTES[3]["backend_status"] == "not_configured"
    assert DEFAULT_MARA_ROUTES[3]["requires_backend_config"] is True
    assert DEFAULT_MARA_ROUTES[3]["missing_backends"] == [
        "colpali",
        "visual_generator",
    ]
    assert DEFAULT_MARA_ROUTES[4]["allowed_routes"] == ["doc_element"]
    assert DEFAULT_MARA_ROUTES[4]["implementation_stage"] == (
        "prototype_element_metadata_index"
    )
    assert DEFAULT_MARA_ROUTES[5]["graph_mode"] == "local"
    assert DEFAULT_MARA_ROUTES[5]["implementation_stage"] == (
        "prototype_lightweight_graph_selector"
    )
    assert DEFAULT_MARA_ROUTES[6]["graph_mode"] == "global"
    assert DEFAULT_MARA_ROUTES[6]["implementation_stage"] == (
        "prototype_lightweight_graph_selector"
    )
    assert DEFAULT_MARA_ROUTES[8]["controller_mode"] == "llm"
    assert DEFAULT_MARA_ROUTES[9]["verification_mode"] == "strict"


def test_load_v2_manifest_preserves_top_level_ragas_evaluator(tmp_path):
    (tmp_path / "doc.txt").write_text("doc", encoding="utf-8")
    manifest_path = tmp_path / "ragas.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "ragas",
                "documents": [{"document_id": "doc", "path": "doc.txt"}],
                "routes": [
                    {
                        "route_id": "paper",
                        "engine": "direct_paste",
                        "ragas_evaluator": "tests.fixture_ragas",
                    }
                ],
                "examples": [
                    {
                        "example_id": "ex",
                        "document_id": "doc",
                        "question": "What?",
                        "answers": ["doc"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    bundle = load_manifest(manifest_path)

    assert bundle.routes[0]["ragas_evaluator"] == "tests.fixture_ragas"


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
