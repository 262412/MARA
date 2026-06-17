import json
import sys
import types

import pyarrow as pa
import pyarrow.parquet as pq

from benchmark.cli import main
from benchmark.manifest import load_manifest

_JPEG_BYTES = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\xff\xd9"


def _read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _empty_report(config):
    return {
        "summary": {
            "suite_name": config.suite_name,
            "dataset_name": "suite",
            "num_examples": 0,
            "num_documents": 0,
            "avg_em": None,
            "avg_f1": None,
            "avg_anls": None,
            "avg_page_hit": None,
            "avg_citation_recall": None,
            "avg_retrieval_seconds": None,
            "avg_generation_seconds": None,
        },
        "documents": [],
        "predictions": [],
    }


def _run_args(manifest_path):
    return [
        "run",
        "--manifest",
        str(manifest_path),
        "--engine",
        "direct_paste",
        "--scope",
        "multi-document",
        "--route",
        "table",
        "--cost-profile",
        "low-cost",
        "--llm-name",
        "Deepseek",
        "--docqa-citation-mode",
        "off",
        "--reasoning",
        "mara",
        "--agent-mode",
        "thorough",
        "--task-type",
        "quiz",
        "--artifact-type",
        "quiz",
        "--artifact-detail",
        "full",
        "--limit",
        "25",
        "--sample-seed",
        "1234",
        "--shard-index",
        "1",
        "--num-shards",
        "4",
    ]


def test_run_cli_writes_v2_route_options_into_config(monkeypatch, tmp_path):
    captured = {}

    def fake_run_benchmark(manifest_path, config):
        captured["manifest_path"] = manifest_path
        captured["config"] = config
        return _empty_report(config)

    def fake_write_reports(report, output_dir, suite_name, *, artifact_detail):
        captured["report"] = report
        captured["artifact_detail"] = artifact_detail
        return tmp_path / "run"

    monkeypatch.setitem(
        sys.modules,
        "benchmark.runner",
        types.SimpleNamespace(run_benchmark=fake_run_benchmark),
    )
    monkeypatch.setitem(
        sys.modules,
        "benchmark.reports",
        types.SimpleNamespace(write_reports=fake_write_reports),
    )

    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text('{"examples": []}', encoding="utf-8")

    exit_code = main(_run_args(manifest_path))

    assert exit_code == 0
    assert captured["config"].engine == "direct_paste"
    assert captured["config"].scope == "multi_document"
    assert captured["config"].route == "table"
    assert captured["config"].cost_profile == "low-cost"
    assert captured["config"].llm_name == "Deepseek"
    assert captured["config"].docqa_citation_mode == "off"
    assert captured["config"].reasoning_type == "mara"
    assert captured["config"].agent_mode == "thorough"
    assert captured["config"].task_type == "quiz"
    assert captured["config"].artifact_type == "quiz"
    assert captured["config"].artifact_detail == "full"
    assert captured["artifact_detail"] == "full"
    assert captured["config"].limit == 25
    assert captured["config"].sample_seed == 1234
    assert captured["config"].shard_index == 1
    assert captured["config"].num_shards == 4


def test_rescore_artifact_cli_writes_mara_scores_without_mutating_source(tmp_path):
    source_run = tmp_path / "source-run"
    source_run.mkdir()
    source_summary = {
        "suite_name": "Original Suite",
        "dataset_name": "qasper-formal",
        "num_examples": 1,
        "num_documents": 1,
        "avg_f1": 0.05,
    }
    (source_run / "summary.json").write_text(
        json.dumps(source_summary),
        encoding="utf-8",
    )
    (source_run / "predictions.jsonl").write_text(
        json.dumps(
            {
                "example_id": "ex-1",
                "route": "controller_auto",
                "benchmark_role": "qa_quality",
                "metrics": {
                    "em": 0.0,
                    "f1": 0.05,
                    "anls": 0.0,
                    "page_hit": 1.0,
                    "span_recall": 1.0,
                    "citation_recall": 1.0,
                    "citation_precision": 1.0,
                    "unsupported_claim_rate": 0.0,
                    "contradiction_count": 0.0,
                    "false_abstention": 0.0,
                },
                "diagnostics": {"controller_route_match": 1.0},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (source_run / "documents.json").write_text("[]", encoding="utf-8")

    output_dir = tmp_path / "rescored"
    exit_code = main(
        [
            "rescore-artifact",
            "--run-dir",
            str(source_run),
            "--output-dir",
            str(output_dir),
            "--suite-name",
            "Rescored Suite",
        ]
    )

    assert exit_code == 0
    assert json.loads((source_run / "summary.json").read_text(encoding="utf-8")) == (
        source_summary
    )
    [rescored_run] = list(output_dir.iterdir())
    summary = json.loads((rescored_run / "summary.json").read_text(encoding="utf-8"))
    predictions = _read_jsonl(rescored_run / "predictions.jsonl")
    assert summary["avg_f1"] == 0.05
    assert summary["avg_mara_score"] == 0.85
    assert summary["mara_rescore_source_run_dir"] == str(source_run.resolve())
    assert predictions[0]["metrics"]["f1"] == 0.05
    assert predictions[0]["metrics"]["mara_score"] == 0.85


def test_apply_route_template_cli_writes_runnable_manifest(tmp_path):
    (tmp_path / "doc.txt").write_text("doc text", encoding="utf-8")
    manifest_path = tmp_path / "base.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "qasper",
                "documents": [
                    {
                        "document_id": "doc",
                        "path": "doc.txt",
                        "format_type": "txt",
                    }
                ],
                "examples": [
                    {
                        "example_id": "ex",
                        "document_ids": ["doc"],
                        "question": "Question?",
                        "answers": ["Answer"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    template_path = tmp_path / "template.json"
    template_path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "template",
                "documents": [],
                "examples": [],
                "routes": [
                    {
                        "route_id": "crag_guarded",
                        "engine": "docqa_runtime",
                        "scope": "multi_document",
                        "verification_mode": "strict",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "routes.json"

    exit_code = main(
        [
            "apply-route-template",
            "--manifest",
            str(manifest_path),
            "--template",
            str(template_path),
            "--output",
            str(output_path),
            "--dataset-name",
            "qasper_plan5_text_main",
        ]
    )

    assert exit_code == 0
    bundle = load_manifest(output_path)
    assert bundle.dataset_name == "qasper_plan5_text_main"
    assert list(bundle.documents) == ["doc"]
    assert [route["route_id"] for route in bundle.routes] == ["crag_guarded"]
    assert bundle.routes[0]["verification_mode"] == "strict"


def test_normalize_slidevqa_parquet_cli_writes_manifest(tmp_path):
    source_path = tmp_path / "slidevqa.parquet"
    image_type = pa.struct([("bytes", pa.binary()), ("path", pa.string())])
    pq.write_table(
        pa.table(
            {
                "deck_name": ["deck"],
                "page_1": pa.array(
                    [{"bytes": _JPEG_BYTES, "path": None}],
                    type=image_type,
                ),
                "qa_id": pa.array([1], type=pa.int64()),
                "question": ["What is shown?"],
                "answer": ["a chart"],
                "evidence_pages": pa.array([[1]], type=pa.list_(pa.int64())),
            }
        ),
        source_path,
    )
    output_path = tmp_path / "slidevqa_manifest.json"

    exit_code = main(
        [
            "normalize-slidevqa-parquet",
            "--source",
            str(source_path),
            "--output",
            str(output_path),
        ]
    )

    assert exit_code == 0
    bundle = load_manifest(output_path)
    assert bundle.dataset_name == "slidevqa"
    assert list(bundle.documents) == ["deck_page_1"]
    assert bundle.examples[0].document_ids == ["deck_page_1"]
