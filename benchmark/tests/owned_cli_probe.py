"""Real CLI/runner/scorer with an explicit, local-only model boundary."""

import contextlib
import hashlib
import io
import json
import runpy
import sys
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


class OwnedModel:
    def __init__(self, root):
        self.root = root

    def __call__(self, prompt, **kwargs):
        marker = next(
            item
            for item in ("SUCCESS", "ABSTAIN", "ERROR", "TIMEOUT")
            if f"OWNED_{item}" in prompt
        )
        with (self.root / "model-calls.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"marker": marker, "generation": kwargs}) + "\n")
        if marker == "ERROR":
            raise RuntimeError("owned model failure")
        if marker == "TIMEOUT":
            time.sleep(1.2)
        return SimpleNamespace(
            text="Insufficient evidence." if marker == "ABSTAIN" else "42"
        )


def manifest(root):
    (root / "自有语料.txt").write_text(
        "The owned observation records 42 participants.", encoding="utf-8"
    )
    path = root / "manifest.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 2,
                "dataset_name": "owned-entry-contract",
                "documents": [{"document_id": "owned-doc", "path": "自有语料.txt"}],
                "examples": [
                    {
                        "example_id": f"ex-{index}",
                        "document_id": "owned-doc",
                        "question": f"OWNED_{kind}: how many participants in the observation?",
                        "answers": [
                            "Insufficient evidence." if kind == "ABSTAIN" else "42"
                        ],
                        "evidence_sources": ["自有语料.txt#page:-"],
                        "metadata": {"unanswerable": kind == "ABSTAIN"},
                    }
                    for index, kind in enumerate(
                        [
                            "SUCCESS",
                            "ABSTAIN",
                            "ERROR",
                            "SUCCESS",
                            "SUCCESS",
                            "SUCCESS",
                            "SUCCESS",
                            "SUCCESS",
                        ]
                    )
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def entry(root, name, args):
    # Reports intentionally reject same-second output collisions. Schedule each
    # command once in the next timestamp slot; never retry a failed invocation.
    slot = datetime.now().strftime("%Y%m%d_%H%M%S")
    deadline = time.monotonic() + 2
    while datetime.now().strftime("%Y%m%d_%H%M%S") == slot:
        assert time.monotonic() < deadline
        time.sleep(0.02)
    sys.argv = ["benchmark", *map(str, args)]
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        try:
            runpy.run_module("benchmark", run_name="__main__")
        except SystemExit as exc:
            assert exc.code in (None, 0), stdout.getvalue()
    (root / f"{name}.stdout").write_text(stdout.getvalue(), encoding="utf-8")
    line = stdout.getvalue().splitlines()[-1]
    run_dir = Path(line.split("written to ", 1)[1])
    return {"argv": sys.argv, "exit_code": 0, "run_dir": str(run_dir)}


def exercise(root):
    from benchmark.system import KotaemonTextRAGSystem

    model = OwnedModel(root)
    with patch.object(KotaemonTextRAGSystem, "_resolve_llm", return_value=model):
        run_commands(root)


def run_commands(root):
    source = manifest(root)
    base = [
        "run",
        "--manifest",
        source,
        "--suite-name",
        "owned-contract",
        "--output-dir",
        root / "runs",
        "--retrieval-mode",
        "text",
        "--scope",
        "multi-document",
        "--benchmark-answer-mode",
        "product",
    ]
    receipts = {}
    for name, options in {
        "warm-first": ["--cache-mode", "warm", "--artifact-detail", "full"],
        "warm-second": ["--cache-mode", "warm", "--artifact-detail", "compact"],
        "cold": ["--cache-mode", "cold"],
        "bypass": ["--cache-mode", "bypass"],
        "sampled-alias": [
            "--engine",
            "kotaemon-text-rag",
            "--sample-seed",
            "7",
            "--shard-index",
            "1",
            "--num-shards",
            "2",
            "--limit",
            "2",
        ],
    }.items():
        receipts[name] = entry(root, name, [*base, *options])
    receipts["rescore"] = rescore_without_mutating(
        root, receipts["warm-first"]["run_dir"]
    )
    receipts["budget"] = budget_command(root, base, source)
    (root / "receipt.json").write_text(json.dumps(receipts, indent=2), encoding="utf-8")


def rescore_without_mutating(root, run_dir):
    original = Path(run_dir)
    source_hashes = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in original.iterdir()
        if p.is_file()
    }
    receipt = entry(
        root,
        "rescore",
        [
            "rescore-artifact",
            "--run-dir",
            run_dir,
            "--output-dir",
            root / "rescored",
            "--suite-name",
            "owned-rescored",
        ],
    )
    assert source_hashes == {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in original.iterdir()
        if p.is_file()
    }
    return receipt


def budget_command(root, base, source):
    # A separate, warm-cache single example reaches the model before the budget
    # is exceeded. Windows records the late return; POSIX may interrupt the call.
    data = json.loads(source.read_text(encoding="utf-8"))
    data["examples"] = [
        {**data["examples"][0], "question": "OWNED_TIMEOUT participants"}
    ]
    budget = root / "budget.json"
    budget.write_text(json.dumps(data), encoding="utf-8")
    return entry(
        root,
        "budget",
        [
            *base,
            "--manifest",
            budget,
            "--route-timeout-seconds",
            "1",
        ],
    )


def main():
    from pytest_runtime_isolation import start_process_test_runtime

    root = Path(sys.argv[1]).resolve()
    runtime = start_process_test_runtime(evidence_dir=root)
    (root / "runtime.json").write_text(json.dumps({"root": str(runtime.paths.root)}))
    # The parent removes this owned root only after this process has exited.
    # Deep-copied reader caches can still hold native handles until process exit.
    exercise(root)


if __name__ == "__main__":
    main()
