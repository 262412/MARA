from __future__ import annotations

import json

from benchmark.jsonl import read_jsonl
from benchmark.reports import write_reports


def test_write_reports_publishes_optional_semantic_debug_artifact(tmp_path):
    report = {
        "summary": {
            "suite_name": "QASPER Debug Suite",
            "dataset_name": "qasper_typed_v2",
            "num_examples": 1,
            "num_documents": 1,
        },
        "predictions": [
            {
                "example_id": "example-1",
                "route": "text_rag",
                "engine_terminal_evidence_bundle": {
                    "metadata": {
                        "semantic_proposition_verifier": {
                            "status": "parsed",
                            "audit_status": "verified",
                            "debug_trace": {
                                "contract_id": "semantic_proposition_debug_trace.v1",
                                "events": [],
                            },
                        },
                        "semantic_proposition_authority": {
                            "status": "rejected",
                            "reason": "semantic_premise_fragment_invalid",
                        },
                    }
                },
            }
        ],
        "documents": [],
    }

    run_dir = write_reports(report, tmp_path, "QASPER Debug Suite")

    assert len(read_jsonl(run_dir / "semantic_debug_traces.jsonl")) == 1
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert summary["qasper_semantic_debug_trace_count"] == 1
    manifest = json.loads(
        (run_dir / "artifact_manifest.json").read_text(encoding="utf-8")
    )
    assert "semantic_debug_traces.jsonl" in manifest["required_files"]
    assert manifest["files"]["semantic_debug_traces.jsonl"]["line_count"] == 1
    assert "Semantic Debug Traces: `semantic_debug_traces.jsonl`" in (
        run_dir / "report.md"
    ).read_text(encoding="utf-8")
