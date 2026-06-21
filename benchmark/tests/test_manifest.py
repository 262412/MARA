import json
from pathlib import Path

from benchmark.manifest import DEFAULT_MARA_ROUTES, load_manifest
from benchmark.normalizers import (
    normalize_financebench_manifest,
    normalize_format_robustness_manifest,
)

CONTROLLER_ALLOWED_ROUTES = [
    "doc_text",
    "hybrid",
    "doc_page_image",
    "doc_element",
    "graph_global",
]


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
                "financebench_id": "financebench_id_1",
                "doc_name": "company_a.pdf",
                "question": "What is revenue?",
                "answer": "10",
                "company": "Company A",
                "doc_type": "10k",
                "doc_period": 2024,
                "evidence": [
                    {
                        "evidence_text": "Revenue was 10.",
                        "evidence_page_num": 12,
                        "evidence_text_full_page": "Full page text should not be gold.",
                    }
                ],
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
    assert bundle.examples[0].example_id == "financebench_id_1"
    assert bundle.examples[0].evidence_pages == [12]
    assert bundle.examples[0].evidence_sources == ["company_a#page:12"]
    assert bundle.examples[0].gold_evidence == [
        {
            "document_id": "company_a",
            "page": 12,
            "citation": "company_a#page:12",
            "span": "Revenue was 10.",
        }
    ]
    assert bundle.examples[0].metadata == {
        "doc_name": "company_a.pdf",
        "company": "Company A",
        "doc_type": "10k",
        "doc_period": 2024,
        "question_type": None,
        "question_reasoning": None,
    }


def test_load_manifest_recovers_legacy_financebench_stringified_evidence(tmp_path):
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
                        "question": "What is capex?",
                        "answers": ["42"],
                        "evidence_sources": [
                            "{'evidence_text': 'Capex was 42.', "
                            "'evidence_page_num': 7, "
                            "'evidence_text_full_page': 'Long page text.'}"
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    example = load_manifest(manifest_path).examples[0]

    assert example.evidence_pages == [7]
    assert example.evidence_sources == ["legacy#page:7"]
    assert example.gold_evidence == [
        {
            "document_id": "legacy",
            "page": 7,
            "citation": "legacy#page:7",
            "span": "Capex was 42.",
        }
    ]


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
                        "verification_domain": "finance",
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
    assert bundle.routes[0]["verification_domain"] == "finance"
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
                        "docqa_citation_mode": "inline",
                        "planner_model": "gpt-4o-mini",
                        "allowed_routes": ["doc_text", "graph_global"],
                        "graph_mode": "local",
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
    assert route["docqa_citation_mode"] == "inline"
    assert route["graph_mode"] == "local"


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
    assert DEFAULT_MARA_ROUTES[0]["engine"] == "benchmark_direct_answer"
    assert DEFAULT_MARA_ROUTES[0]["route_policy"] == "direct"
    assert DEFAULT_MARA_ROUTES[0]["benchmark_role"] == "diagnostic"
    assert DEFAULT_MARA_ROUTES[1]["benchmark_role"] == "qa_quality"
    assert all(
        route["docqa_citation_mode"] == "inline" for route in DEFAULT_MARA_ROUTES
    )
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
    assert DEFAULT_MARA_ROUTES[5]["benchmark_role"] == "prototype"
    assert DEFAULT_MARA_ROUTES[5]["implementation_stage"] == (
        "prototype_lightweight_graph_selector"
    )
    assert DEFAULT_MARA_ROUTES[6]["graph_mode"] == "global"
    assert DEFAULT_MARA_ROUTES[6]["implementation_stage"] == (
        "prototype_lightweight_graph_selector"
    )
    assert DEFAULT_MARA_ROUTES[8]["controller_mode"] == "llm"
    assert DEFAULT_MARA_ROUTES[8]["allowed_routes"] == CONTROLLER_ALLOWED_ROUTES
    assert DEFAULT_MARA_ROUTES[8]["benchmark_role"] == "qa_quality"
    assert DEFAULT_MARA_ROUTES[9]["verification_mode"] == "strict"
    assert DEFAULT_MARA_ROUTES[9]["benchmark_role"] == "qa_quality"


def test_manifest_templates_load_expected_mara_route_sets():
    template_dir = Path("benchmark/manifests/templates")
    all_routes = load_manifest(template_dir / "mara_all_routes.local.json")
    text_only = load_manifest(template_dir / "mara_text_only.json")
    multimodal = load_manifest(template_dir / "mara_multimodal.json")

    assert [route["route_id"] for route in all_routes.routes] == [
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
    assert [route["route_id"] for route in text_only.routes] == [
        "direct_answer",
        "text_rag",
        "controller_auto",
        "crag_guarded",
    ]
    assert [route["route_id"] for route in multimodal.routes] == [
        "text_rag",
        "page_image_rag_vlm",
        "element_rag",
        "hybrid_rag",
        "controller_auto",
    ]
    assert all_routes.routes[2]["route_id"] == "page_image_rag_smoke"
    assert all_routes.routes[2]["visual_backend_type"] == "deterministic_smoke"
    assert all_routes.routes[2]["implementation_stage"] == (
        "deterministic_page_image_smoke"
    )
    assert all_routes.routes[3]["visual_retriever_backend"] == "colqwen"
    assert all_routes.routes[3]["visual_generator_backend"] == "local_qwen3_vl"
    assert all_routes.routes[3]["generator_backend"] == "local_qwen3_vl"
    assert {
        route["route_id"]: route["benchmark_role"] for route in text_only.routes
    } == {
        "direct_answer": "diagnostic",
        "text_rag": "qa_quality",
        "controller_auto": "qa_quality",
        "crag_guarded": "qa_quality",
    }
    assert {
        route["route_id"]: route["docqa_citation_mode"] for route in text_only.routes
    } == {
        "direct_answer": "inline",
        "text_rag": "inline",
        "controller_auto": "inline",
        "crag_guarded": "inline",
    }
    assert all_routes.routes[5]["route_id"] == "graph_rag_local"
    assert all_routes.routes[5]["benchmark_role"] == "prototype"
    assert all_routes.routes[6]["route_id"] == "graph_rag_global"
    assert all_routes.routes[6]["graph_mode"] == "global"
    assert all_routes.routes[7]["route_id"] == "hybrid_rag"
    assert all_routes.routes[7]["benchmark_role"] == "qa_quality"
    assert all_routes.routes[8]["allowed_routes"] == CONTROLLER_ALLOWED_ROUTES
    assert text_only.routes[2]["allowed_routes"] == CONTROLLER_ALLOWED_ROUTES
    assert multimodal.routes[4]["allowed_routes"] == CONTROLLER_ALLOWED_ROUTES
    assert all_routes.routes[8]["controller_mode"] == "llm"
    assert text_only.routes[2]["controller_mode"] == "llm"
    assert multimodal.routes[4]["controller_mode"] == "llm"


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
