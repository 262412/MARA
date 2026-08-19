from __future__ import annotations

import json
from pathlib import Path

from benchmark.execution_plan import JobDefinition, build_execution_plan
from benchmark.reports import write_reports
from benchmark.synthesis import synthesize_execution_plan


def _manifest(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "plan_test",
                "documents": [{"document_id": "doc", "path": "doc.pdf"}],
                "examples": [
                    {
                        "example_id": f"example-{index}",
                        "document_ids": ["doc"],
                        "question": "question",
                        "answers": ["answer"],
                    }
                    for index in range(4)
                ],
                "routes": [{"route_id": "text"}, {"route_id": "controller"}],
            }
        ),
        encoding="utf-8",
    )


def test_execution_plan_freezes_selected_ids_and_complete_execution_manifest(tmp_path):
    manifest = tmp_path / "manifest.json"
    _manifest(manifest)
    definitions = [
        JobDefinition(
            "text",
            "plan_test",
            "all",
            0,
            2,
            2,
            60,
            "plan-test-shard0",
            manifest,
            tmp_path / "artifacts",
        ),
        JobDefinition(
            "text",
            "plan_test",
            "all",
            1,
            2,
            2,
            60,
            "plan-test-shard1",
            manifest,
            tmp_path / "artifacts",
        ),
    ]

    plan = build_execution_plan(
        definitions,
        output_plan=tmp_path / "plan.json",
        output_table=tmp_path / "jobs.tsv",
        source_sha="clean-sha",
        sample_seed=7,
    )

    group = plan["groups"][0]
    assert group["selected_example_count"] == 4
    assert group["expected_full_key_count"] == 8
    execution_manifest = json.loads(
        Path(group["execution_manifest"]).read_text(encoding="utf-8")
    )
    assert len(execution_manifest["examples"]) == 4
    assert [route["route_id"] for route in execution_manifest["routes"]] == [
        "text",
        "controller",
    ]
    table_header = (tmp_path / "jobs.tsv").read_text(encoding="utf-8").splitlines()[0]
    assert "selected_example_ids_json" in table_header
    assert "expected_keys_json" in table_header
    assert "artifact_digest" in table_header


def test_synthesis_rejects_missing_shard_key(tmp_path):
    manifest = tmp_path / "manifest.json"
    _manifest(manifest)
    output_root = tmp_path / "artifacts"
    definitions = [
        JobDefinition(
            "text",
            "plan_test",
            "all",
            0,
            2,
            2,
            60,
            "plan-test-shard0",
            manifest,
            output_root,
        ),
        JobDefinition(
            "text",
            "plan_test",
            "all",
            1,
            2,
            2,
            60,
            "plan-test-shard1",
            manifest,
            output_root,
        ),
    ]
    plan = build_execution_plan(
        definitions,
        output_plan=tmp_path / "plan.json",
        output_table=tmp_path / "jobs.tsv",
        source_sha="clean-sha",
        sample_seed=7,
    )
    first = plan["jobs"][0]
    write_reports(
        {
            "summary": {
                "suite_name": first["suite_name"],
                "dataset_name": "plan_test",
                "num_examples": len(first["selected_example_ids"]),
                "num_documents": 1,
            },
            "predictions": [
                {"example_id": example_id, "route": route, "error": None}
                for example_id, route in first["expected_keys"]
            ],
            "documents": [],
        },
        output_root,
        first["suite_name"],
    )

    try:
        synthesize_execution_plan(
            tmp_path / "plan.json",
            tmp_path / "synthesis",
            table_path=tmp_path / "jobs.tsv",
            require_all_usable=True,
        )
    except SystemExit as exc:
        assert "benchmark synthesis failed" in str(exc)
    else:
        raise AssertionError("synthesis unexpectedly accepted a missing shard")
    synthesis = json.loads(
        (tmp_path / "synthesis" / "synthesis.json").read_text(encoding="utf-8")
    )
    assert synthesis["valid"] is False
    assert synthesis["union_key_count"] == 2
    assert synthesis["overlap_key_count"] == 0
    assert synthesis["missing_key_count"] == 2
    assert synthesis["unexpected_key_count"] == 0


def test_synthesis_streams_shards_into_atomic_group_artifact(tmp_path):
    manifest = tmp_path / "manifest.json"
    _manifest(manifest)
    output_root = tmp_path / "artifacts"
    definitions = [
        JobDefinition(
            "text",
            "plan_test",
            "all",
            shard_index,
            2,
            2,
            60,
            f"plan-test-shard{shard_index}",
            manifest,
            output_root,
        )
        for shard_index in range(2)
    ]
    plan = build_execution_plan(
        definitions,
        output_plan=tmp_path / "plan.json",
        output_table=tmp_path / "jobs.tsv",
        source_sha="clean-sha",
        sample_seed=7,
    )

    for job in plan["jobs"]:
        write_reports(
            {
                "summary": {
                    "suite_name": job["suite_name"],
                    "dataset_name": "plan_test",
                    "num_examples": len(job["selected_example_ids"]),
                    "num_documents": 1,
                },
                "predictions": [
                    {"example_id": example_id, "route": route, "error": None}
                    for example_id, route in job["expected_keys"]
                ],
                "documents": [],
            },
            output_root,
            job["suite_name"],
        )

    synthesis = synthesize_execution_plan(
        tmp_path / "plan.json",
        tmp_path / "synthesis",
        table_path=tmp_path / "jobs.tsv",
        require_all_usable=True,
    )

    assert synthesis["valid"] is True
    assert synthesis["completed_job_count"] == 2
    assert synthesis["expected_union_key_count"] == 8
    assert synthesis["union_key_count"] == 8
    assert synthesis["overlap_key_count"] == 0
    assert synthesis["missing_key_count"] == 0
    assert synthesis["unexpected_key_count"] == 0
