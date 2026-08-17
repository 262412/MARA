from __future__ import annotations

import json

from benchmark.jsonl import read_jsonl
from benchmark.reports import write_reports

EXPECTED_COMPACT_LIMITS = {
    "max_evidence_text_chars": 2000,
    "max_prediction_evidence_items": 10,
    "max_trace_events": 20,
    "max_candidate_identity_items": 80,
    "max_reranked_identity_items": 30,
}


def _read_jsonl(path):
    return read_jsonl(path)


def test_write_reports_does_not_leave_summary_when_raw_artifact_write_fails(
    tmp_path, monkeypatch
):
    from benchmark import reports

    report = {
        "summary": {
            "suite_name": "Interrupted Suite",
            "dataset_name": "sample",
            "num_examples": 1,
            "num_documents": 1,
        },
        "predictions": [{"example_id": "ex-1", "prediction": "42"}],
        "documents": [{"document_id": "doc-1", "path": "doc.pdf"}],
    }

    original_write_jsonl = reports._write_jsonl

    def fail_prediction_write(path, rows):
        if path.name == "predictions.jsonl":
            raise RuntimeError("simulated interrupted write")
        original_write_jsonl(path, rows)

    monkeypatch.setattr(reports, "_write_jsonl", fail_prediction_write)

    try:
        reports.write_reports(report, tmp_path, "Interrupted Suite")
    except RuntimeError:
        pass
    else:
        raise AssertionError("write_reports unexpectedly succeeded")

    run_dirs = list(tmp_path.iterdir())
    assert len(run_dirs) == 1
    assert not (run_dirs[0] / "summary.json").exists()


def test_write_reports_emits_required_artifacts_with_jsonl_and_route_metadata(tmp_path):
    report = {
        "summary": {
            "suite_name": "Phase 2 Suite",
            "dataset_name": "sample",
            "num_examples": 1,
            "num_documents": 1,
            "avg_em": 1.0,
            "avg_f1": 1.0,
            "avg_anls": 1.0,
            "avg_page_hit": 1.0,
            "avg_citation_recall": 1.0,
            "avg_abstention_rate": 0.0,
            "avg_false_abstention": 0.0,
            "avg_markdown_table_renderable": 1.0,
            "avg_latex_renderable": 1.0,
            "avg_rewrite_skipped": 1.0,
            "avg_guardrail_expectation_match": 1.0,
            "avg_retrieval_seconds": 0.2,
            "avg_generation_seconds": 0.4,
            "engine": "local",
            "route": "hybrid",
            "scope": "smoke",
        },
        "config": {
            "engine": "config-engine",
            "route": "config-route",
            "scope": "config-scope",
        },
        "predictions": [
            {"example_id": "ex-1", "prediction": "42"},
        ],
        "documents": [{"document_id": "doc-1", "path": "doc.pdf"}],
        "retrieval_traces": [
            {"example_id": "ex-1", "hits": [{"document_id": "doc-1", "page": 3}]}
        ],
    }

    run_dir = write_reports(report, tmp_path, "Phase 2 Suite")

    assert sorted(path.name for path in run_dir.iterdir()) == [
        "artifact_complete.json",
        "artifact_manifest.json",
        "documents.json",
        "predictions.jsonl",
        "report.md",
        "retrieval_traces.jsonl",
        "summary.json",
    ]
    summary = report["summary"]
    assert isinstance(summary, dict)
    expected_summary = {
        **summary,
        "artifact_detail": "compact",
        "artifact_limits": EXPECTED_COMPACT_LIMITS,
    }
    assert (
        json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        == expected_summary
    )
    assert _read_jsonl(run_dir / "predictions.jsonl") == report["predictions"]
    assert (
        json.loads((run_dir / "documents.json").read_text(encoding="utf-8"))
        == report["documents"]
    )
    assert _read_jsonl(run_dir / "retrieval_traces.jsonl") == report["retrieval_traces"]
    markdown = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "predictions.jsonl" in markdown
    assert "retrieval_traces.jsonl" in markdown
    assert "documents.json" in markdown
    assert "- Engine: `local`" in markdown
    assert "- Route: `hybrid`" in markdown
    assert "- Scope: `smoke`" in markdown
    assert "- False Abstention: `0.0`" in markdown
    assert "- Markdown Table Renderable: `1.0`" in markdown
    assert "- LaTeX Renderable: `1.0`" in markdown
    assert "- Guardrail Expectation Match: `1.0`" in markdown


def test_write_reports_defaults_to_compact_artifacts(tmp_path):
    large_text = "x" * 1_000_000
    report = {
        "summary": {
            "suite_name": "Compact Suite",
            "dataset_name": "sample",
            "num_examples": 1,
            "num_documents": 1,
        },
        "predictions": [
            {
                "example_id": "ex-1",
                "evidence_bundle": {
                    "items": [
                        {
                            "evidence_id": f"hit-{index}",
                            "text": large_text,
                            "snippet": large_text,
                        }
                        for index in range(12)
                    ]
                },
                "retrieval_trace": [
                    {"event": f"trace-{index}", "text": large_text}
                    for index in range(25)
                ],
                "agent_trace": [
                    {"event": f"agent-{index}", "text": large_text}
                    for index in range(25)
                ],
            }
        ],
        "documents": [],
    }

    run_dir = write_reports(report, tmp_path, "Compact Suite")
    prediction = _read_jsonl(run_dir / "predictions.jsonl")[0]
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))

    assert summary["artifact_detail"] == "compact"
    assert summary["artifact_limits"] == EXPECTED_COMPACT_LIMITS
    assert len(prediction["evidence_bundle"]["items"]) == 10
    assert len(prediction["evidence_bundle"]["items"][0]["text"]) <= 2000
    assert len(prediction["evidence_bundle"]["items"][0]["snippet"]) <= 2000
    assert len(prediction["retrieval_trace"]) == 20
    assert len(prediction["agent_trace"]) == 20


def test_write_reports_compacts_nested_runtime_indexes(tmp_path):
    large_text = "x" * 1_000_000
    heavy_record = {
        "evidence_id": "page-image:file-1:1",
        "image_origin": large_text,
        "page_image_path": large_text,
        "rendered_page_image": large_text,
        "text": large_text,
        "metadata": {
            "image_origin": large_text,
            "image_ref": large_text,
            "multi_vector_representation": [float(index) for index in range(256)],
            "visual_embedding": [float(index) for index in range(256)],
            "late_interaction_tokens": [f"token-{index}" for index in range(256)],
        },
    }
    report = {
        "summary": {
            "suite_name": "Nested Compact Suite",
            "dataset_name": "sample",
            "num_examples": 1,
            "num_documents": 1,
        },
        "predictions": [
            {
                "example_id": "ex-1",
                "retrieved_hits": [
                    {"evidence_id": f"hit-{index}", "text": large_text}
                    for index in range(12)
                ],
                "evidence_metadata": {
                    "page_image_index": [
                        {**heavy_record, "evidence_id": f"page-{index}"}
                        for index in range(12)
                    ],
                    "visual_retriever_scores": {
                        f"page-{index}": float(index) for index in range(12)
                    },
                },
                "evidence_bundle": {
                    "items": [
                        {"evidence_id": f"bundle-{index}", "text": large_text}
                        for index in range(12)
                    ],
                    "metadata": {
                        "page_image_index": [
                            {**heavy_record, "evidence_id": f"bundle-page-{index}"}
                            for index in range(12)
                        ],
                        "visual_retriever_scores": {
                            f"bundle-page-{index}": float(index) for index in range(12)
                        },
                    },
                },
            }
        ],
        "documents": [],
    }

    run_dir = write_reports(report, tmp_path, "Nested Compact Suite")
    prediction = _read_jsonl(run_dir / "predictions.jsonl")[0]
    trace = _read_jsonl(run_dir / "retrieval_traces.jsonl")[0]

    assert len(prediction["retrieved_hits"]) == 10
    assert len(prediction["evidence_metadata"]["page_image_index"]) == 10
    assert len(prediction["evidence_metadata"]["visual_retriever_scores"]) == 10
    assert len(prediction["evidence_bundle"]["metadata"]["page_image_index"]) == 10
    first_record = prediction["evidence_metadata"]["page_image_index"][0]
    assert len(first_record["text"]) <= 2000
    assert "image_origin" not in first_record
    assert "page_image_path" not in first_record
    assert "rendered_page_image" not in first_record
    assert "image_origin" not in first_record["metadata"]
    assert "image_ref" not in first_record["metadata"]
    assert "multi_vector_representation" not in first_record["metadata"]
    assert "visual_embedding" not in first_record["metadata"]
    assert "late_interaction_tokens" not in first_record["metadata"]
    assert len(trace["retrieved_hits"]) == 10
    assert len(trace["evidence_metadata"]["page_image_index"]) == 10


def test_write_reports_compacts_large_source_backrefs(tmp_path):
    source_backrefs = [f"doc#page:{index}" for index in range(200)]
    report = {
        "summary": {
            "suite_name": "Source Backrefs Compact Suite",
            "dataset_name": "sample",
            "num_examples": 1,
            "num_documents": 1,
        },
        "predictions": [
            {
                "example_id": "ex-1",
                "retrieved_hits": [
                    {
                        "evidence_id": "hit-1",
                        "source_backrefs": source_backrefs,
                    }
                ],
                "evidence_bundle": {
                    "items": [
                        {
                            "evidence_id": "bundle-hit-1",
                            "source_backrefs": source_backrefs,
                        }
                    ]
                },
            }
        ],
        "documents": [],
    }

    run_dir = write_reports(report, tmp_path, "Source Backrefs Compact Suite")
    prediction = _read_jsonl(run_dir / "predictions.jsonl")[0]

    assert len(prediction["retrieved_hits"][0]["source_backrefs"]) == 10
    assert len(prediction["evidence_bundle"]["items"][0]["source_backrefs"]) == 10


def test_write_reports_full_artifacts_preserve_large_fields(tmp_path):
    large_text = "x" * 1_000_000
    report = {
        "summary": {
            "suite_name": "Full Suite",
            "dataset_name": "sample",
            "num_examples": 1,
            "num_documents": 1,
        },
        "predictions": [
            {
                "example_id": "ex-1",
                "evidence_bundle": {
                    "items": [
                        {
                            "evidence_id": "hit-1",
                            "text": large_text,
                            "snippet": large_text,
                        }
                    ]
                },
                "agent_trace": [{"event": "agent", "text": large_text}],
            }
        ],
        "documents": [],
    }

    run_dir = write_reports(
        report,
        tmp_path,
        "Full Suite",
        artifact_detail="full",
    )
    prediction = _read_jsonl(run_dir / "predictions.jsonl")[0]
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))

    assert summary["artifact_detail"] == "full"
    assert summary["artifact_limits"] == EXPECTED_COMPACT_LIMITS
    assert prediction["evidence_bundle"]["items"][0]["text"] == large_text
    assert prediction["evidence_bundle"]["items"][0]["snippet"] == large_text
    assert prediction["agent_trace"][0]["text"] == large_text


def test_write_reports_derived_trace_preserves_citation_locator_fields(tmp_path):
    report = {
        "summary": {
            "suite_name": "Trace Citation Suite",
            "dataset_name": "sample",
            "num_examples": 1,
            "num_documents": 1,
        },
        "predictions": [
            {
                "example_id": "ex-1",
                "predicted_pages": ["4"],
                "predicted_sources": ["doc#page:4"],
                "predicted_citations": ["doc#page:4"],
                "scored_predicted_sources": ["doc#page:4"],
                "gold_pages": ["4"],
                "gold_sources": ["doc#page:4"],
                "gold_evidence": [{"citation": "doc#page:4", "page": 4}],
                "retrieved_hits": [
                    {
                        "evidence_id": "hit-1",
                        "source_backrefs": ["doc#page:4"],
                    }
                ],
            }
        ],
        "documents": [],
    }

    run_dir = write_reports(report, tmp_path, "Trace Citation Suite")
    trace = _read_jsonl(run_dir / "retrieval_traces.jsonl")[0]

    assert trace["predicted_pages"] == ["4"]
    assert trace["predicted_sources"] == ["doc#page:4"]
    assert trace["predicted_citations"] == ["doc#page:4"]
    assert trace["scored_predicted_sources"] == ["doc#page:4"]
    assert trace["gold_sources"] == ["doc#page:4"]
    assert trace["gold_evidence"] == [{"citation": "doc#page:4", "page": 4}]


def test_write_reports_lists_skipped_routes(tmp_path):
    report = {
        "summary": {
            "suite_name": "Skip Suite",
            "dataset_name": "sample",
            "num_examples": 1,
            "num_documents": 1,
            "num_executed_routes": 1,
            "num_skipped_routes": 1,
            "skipped_routes": [
                {
                    "route_id": "page_image_rag_vlm",
                    "skip_reason": "not_configured: colpali, visual_generator",
                }
            ],
        },
        "predictions": [],
        "documents": [],
    }

    run_dir = write_reports(report, tmp_path, "Skip Suite")
    markdown = (run_dir / "report.md").read_text(encoding="utf-8")

    assert "- Executed Routes: `1`" in markdown
    assert "- Skipped Routes: `1`" in markdown
    assert (
        "- `page_image_rag_vlm`: not_configured: colpali, visual_generator" in markdown
    )


def test_write_reports_lists_multimodal_backend_health(tmp_path):
    report = {
        "summary": {
            "suite_name": "Backend Health Suite",
            "dataset_name": "sample",
            "num_examples": 1,
            "num_documents": 1,
            "backend_health": {
                "schema_version": 1,
                "overall_status": "blocked",
                "backends": {
                    "text_llm": {
                        "role": "text_llm",
                        "url": "http://127.0.0.1:8000/v1/models",
                        "status": "ready",
                        "models": ["Qwen/Qwen3-8B"],
                    },
                    "vlm": {
                        "role": "vlm",
                        "url": "http://127.0.0.1:8001/v1/models",
                        "status": "blocked",
                        "failure_type": "unreachable",
                    },
                },
                "failure_taxonomy": [
                    {
                        "role": "vlm",
                        "failure_type": "unreachable",
                        "status": "blocked",
                    }
                ],
            },
        },
        "predictions": [],
        "documents": [],
    }

    run_dir = write_reports(report, tmp_path, "Backend Health Suite")
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    markdown = (run_dir / "report.md").read_text(encoding="utf-8")

    assert summary["backend_health"]["failure_taxonomy"] == [
        {
            "role": "vlm",
            "failure_type": "unreachable",
            "status": "blocked",
        }
    ]
    assert "## Multimodal Backend Health" in markdown
    assert "- Overall Status: `blocked`" in markdown
    assert (
        "- `text_llm`: ready; url=`http://127.0.0.1:8000/v1/models`, "
        "models=`Qwen/Qwen3-8B`" in markdown
    )
    assert (
        "- `vlm`: blocked; url=`http://127.0.0.1:8001/v1/models`, "
        "failure_type=`unreachable`" in markdown
    )


def test_write_reports_lists_backend_status_by_route(tmp_path):
    report = {
        "summary": {
            "suite_name": "Backend Suite",
            "dataset_name": "sample",
            "num_examples": 1,
            "num_documents": 1,
            "backend_metadata": {
                "text_rag": {
                    "text_retriever": "docqa_text",
                    "generator_backend": "local_docqa_generator",
                },
                "page_image_rag_vlm": {
                    "backend_status": "not_configured",
                    "visual_retriever": "local_late_interaction",
                    "visual_generator": "evidence_only_without_vlm",
                },
            },
        },
        "predictions": [],
        "documents": [],
    }

    run_dir = write_reports(report, tmp_path, "Backend Suite")
    markdown = (run_dir / "report.md").read_text(encoding="utf-8")

    assert "## Backend Status By Route" in markdown
    assert (
        "- `text_rag`: configured; generator_backend=`local_docqa_generator`, text_retriever=`docqa_text`"
        in markdown
    )
    assert (
        "- `page_image_rag_vlm`: not_configured; visual_generator=`evidence_only_without_vlm`, visual_retriever=`local_late_interaction`"
        in markdown
    )


def test_write_reports_derives_minimal_traces_from_predictions_when_missing(tmp_path):
    report = {
        "summary": {
            "suite_name": "Compat Suite",
            "dataset_name": "sample",
            "num_examples": 2,
            "num_documents": 1,
            "avg_em": 0.0,
            "avg_f1": 0.0,
            "avg_anls": 0.0,
            "avg_page_hit": 0.0,
            "avg_citation_recall": 0.0,
            "avg_retrieval_seconds": 0.0,
            "avg_generation_seconds": 0.0,
        },
        "predictions": [
            {
                "example_id": "with-hits",
                "prediction": "alpha",
                "retrieved_hits": [{"document_id": "doc-1", "score": 0.9}],
            },
            {
                "example_id": "with-trace",
                "prediction": "beta",
                "retrieval_trace": {"hits": [{"document_id": "doc-2"}]},
                "agent_trace": [{"stage": "planner", "decision": "retrieve"}],
                "evidence_metadata": {"has_table_evidence": True},
                "claim_verification": {"abstained": False},
            },
        ],
        "documents": [],
    }

    run_dir = write_reports(report, tmp_path, "Compat Suite")

    assert _read_jsonl(run_dir / "predictions.jsonl") == report["predictions"]
    assert _read_jsonl(run_dir / "retrieval_traces.jsonl") == [
        {
            "example_id": "with-hits",
            "retrieved_hits": [{"document_id": "doc-1", "score": 0.9}],
        },
        {
            "example_id": "with-trace",
            "retrieval_trace": {"hits": [{"document_id": "doc-2"}]},
            "agent_trace": [{"stage": "planner", "decision": "retrieve"}],
            "evidence_metadata": {"has_table_evidence": True},
            "claim_verification": {"abstained": False},
        },
    ]


def test_write_reports_includes_multimodal_summary_metrics(tmp_path):
    report = {
        "summary": {
            "suite_name": "MARA Suite",
            "dataset_name": "sample",
            "num_examples": 1,
            "num_documents": 1,
            "avg_em": 0.0,
            "avg_f1": 0.0,
            "avg_anls": 0.0,
            "avg_page_hit": 0.0,
            "avg_citation_recall": 0.0,
            "avg_table_hit": 1.0,
            "avg_figure_hit": 0.5,
            "avg_formula_hit": 1.0,
            "avg_slide_hit": 0.0,
            "avg_retrieval_seconds": 0.0,
            "avg_generation_seconds": 0.0,
        },
        "predictions": [],
        "documents": [],
    }

    run_dir = write_reports(report, tmp_path, "MARA Suite")

    markdown = (run_dir / "report.md").read_text(encoding="utf-8")
    assert "- Table Hit: `1.0`" in markdown
    assert "- Figure Hit: `0.5`" in markdown
    assert "- Formula Hit: `1.0`" in markdown
    assert "- Slide Hit: `0.0`" in markdown
