"""Installed dependencies, real source CLI, no user model or data access."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from pytest_runtime_isolation import ISOLATED_RUNTIME_ENV_KEYS


def load_run(receipt):
    root = Path(receipt["run_dir"])
    rows = [
        json.loads(line)
        for line in (root / "predictions.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    return root, json.loads((root / "summary.json").read_text(encoding="utf-8")), rows


def business_projection(rows):
    keys = (
        "example_id",
        "document_id",
        "route",
        "engine",
        "scope",
        "gold_answers",
        "predicted_answer",
        "predicted_sources",
        "metrics",
        "error",
    )
    return [{key: row.get(key) for key in keys} for row in rows]


def run_owned_cli(tmp_path, mara_test_runtime_paths):
    root = mara_test_runtime_paths.root
    keys = (*ISOLATED_RUNTIME_ENV_KEYS, "PATH", "SYSTEMROOT", "WINDIR")
    env = {key: os.environ[key] for key in keys if key in os.environ}
    repo = Path(__file__).resolve().parents[2]
    env.update(
        PYTHONPATH=os.pathsep.join(
            map(
                str,
                [
                    repo,
                    repo / "libs/kotaemon",
                    repo / "libs/ktem",
                    repo / "libs/slide_cli",
                ],
            )
        ),
        PYTHONUTF8="1",
        PYTHONDONTWRITEBYTECODE="1",
        MARA_DIAGNOSTIC_ISOLATION_REQUIRED="1",
        MARA_DIAGNOSTIC_CHILD="1",
        MARA_PYTEST_OWNER_TOKEN=(root / ".mara-pytest-owner").read_text(),
        MARA_PYTEST_RUNTIME_PARENT=str(root / "children"),
    )
    for key in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA"):
        env[key] = str(tmp_path)
    # Keep the owned Windows path below MAX_PATH even with cold cache suffixes.
    evidence = root / "benchmark-probe"
    evidence.mkdir()
    command = [
        sys.executable,
        "-B",
        "-m",
        "benchmark.tests.owned_cli_probe",
        str(evidence),
    ]
    process = subprocess.Popen(
        command,
        cwd=tmp_path,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
    )
    try:
        stdout, _ = process.communicate(timeout=120)
        assert process.returncode == 0, stdout
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=10)
    child_root = Path(json.loads((evidence / "runtime.json").read_text())["root"])
    assert child_root.resolve().is_relative_to(root / "children")
    assert (child_root / ".mara-pytest-owner").is_file()
    shutil.rmtree(child_root)
    assert not child_root.exists()
    return evidence


def test_owned_cli_parse_cache_score_and_rescore(tmp_path, mara_test_runtime_paths):
    evidence = run_owned_cli(tmp_path, mara_test_runtime_paths)
    receipts = json.loads((evidence / "receipt.json").read_text())
    runs = {name: load_run(receipt) for name, receipt in receipts.items()}
    assert_business(runs)
    assert_cache_and_selection(runs)
    calls = [
        json.loads(line)
        for line in (evidence / "model-calls.jsonl").read_text().splitlines()
    ]
    assert len(calls) == 35
    assert calls[-1]["marker"] == "TIMEOUT"
    assert all(
        call["generation"] == {"temperature": 0, "top_p": 1, "seed": 20260724}
        for call in calls
    )
    print(
        json.dumps(
            {
                "commands": receipts,
                "model_calls": len(calls),
                "report_hashes": {
                    name: {
                        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                        for path in run[0].iterdir()
                        if path.is_file()
                    }
                    for name, run in runs.items()
                },
            }
        )
    )


def assert_business(runs):
    _path, summary, rows = runs["warm-first"]
    assert [row["example_id"] for row in rows] == [f"ex-{index}" for index in range(8)]
    assert summary["num_examples"] == summary["num_manifest_examples"] == 8
    assert summary["route_metric_table"][0]["num_predictions"] == 8
    assert "owned model failure" in rows[2]["error"]
    assert rows[1]["metrics"]["abstained"] == 1.0
    assert rows[0]["predicted_sources"] == ["自有语料.txt#page:-"]
    assert rows[0]["metrics"]["source_retrieval_recall"] == 1.0
    # Retrieved source identity is not an emitted citation or a page annotation.
    assert rows[0]["metrics"]["citation_recall"] is None
    assert rows[0]["metrics"]["page_hit"] is None
    assert summary["avg_em"] == sum(row["metrics"]["em"] for row in rows) / 8
    for name in ("warm-second", "cold", "bypass"):
        assert business_projection(runs[name][2]) == business_projection(rows)
    assert [row["example_id"] for row in runs["rescore"][2]] == [
        row["example_id"] for row in rows
    ]
    assert [row["predicted_answer"] for row in runs["rescore"][2]] == [
        row["predicted_answer"] for row in rows
    ]
    budget = runs["budget"][2]
    assert len(budget) == 1 and "timed out" in budget[0]["error"]
    for path, _summary, predictions in runs.values():
        assert (path / "report.md").is_file() and (path / "route_metrics.csv").is_file()
        assert all(row["route"] == "all" for row in predictions)


def assert_cache_and_selection(runs):
    for name, expected in {
        "warm-first": {"hits": 0, "misses": 1, "writes": 1},
        "warm-second": {"hits": 1, "misses": 0, "writes": 0},
        "cold": {"hits": 0, "misses": 1, "writes": 1},
        "bypass": {"hits": 0, "misses": 0, "writes": 0},
    }.items():
        assert runs[name][2][0]["cache"]["parse"] == expected
    _path, summary, rows = runs["sampled-alias"]
    assert [row["example_id"] for row in rows] == ["ex-7", "ex-4"]
    assert all(
        row["engine"] == "legacy_text_rag" and row["scope"] == "multi_document"
        for row in rows
    )
    assert summary["num_examples"] == 2 and summary["num_manifest_examples"] == 8
    assert summary["selection"] == {
        "limit": 2,
        "sample_seed": 7,
        "shard_index": 1,
        "num_shards": 2,
    }
